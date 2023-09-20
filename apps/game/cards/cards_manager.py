import json
from typing import Optional
from beanie import PydanticObjectId
from bson import ObjectId


from apps.config import settings
from apps.connections import redis_cache
from apps.game.consumers import external_sio
from apps.game.documents import GamePlayer, GameRound
from apps.game.tasks import send_make_decision_to_starter_game_player

from apps.game.services.custom_exception import ValidationError
from apps.game.cards.base_card_manager import BaseCardManager
from apps.game.cards.hand import Hand
from apps.game.services.utils import get_timestamp, check_if_player_can_double_or_split
from apps.game.services.payment_manager import PaymentManager


class EuropeanCardsManager(BaseCardManager):
    def __init__(self, session_data: dict, round_id: str):
        super().__init__(session_data, round_id)
        self.card: Optional[str] = None
        self.game_round: Optional[GameRound] = None

    async def handle_card_dealing(self, card) -> None:
        self.check_card(card)
        self.card = card
        seats = await redis_cache.get_or_cache_game_player_seats(self.round_id)
        self.game_round: GameRound = await GameRound.get(
            PydanticObjectId(self.round_id)
        )
        self.check_can_scan_card()
        if len(
            self.game_round.dealer_cards
        ) == 1 and self.game_round.card_count + 1 == len(seats):
            await self._save_last_player_card(seats)
            await self.update_card_count()
            return
        elif len(seats) > self.game_round.card_count:
            await self._save_player_card(seats)
            await self.update_card_count()
            return
        await self._save_dealer_card()

    def check_can_scan_card(self) -> None:
        if int(self.game_round.start_timestamp) > get_timestamp():
            raise ValidationError("Betting time is not over")
        elif (
            self.game_round.insurance_timestamp
            and int(self.game_round.insurance_timestamp) > get_timestamp()
        ):
            raise ValidationError("Insurance decision time is not over")

    async def _save_last_player_card(self, seats) -> None:
        await self._save_player_card(seats)
        try:
            if self.game_round.dealer_cards[0][1] == "A":
                insurable_seats = await self.get_insurable_seats()
                if insurable_seats:
                    self.game_round.insurance_timestamp = get_timestamp(
                        settings.ACCEPT_INSURANCE_SECONDS - 1
                    )

                    await external_sio.emit(
                        "make_insurance",
                        {
                            "decision_time": settings.ACCEPT_INSURANCE_SECONDS - 1,
                            "insurable_seats": insurable_seats,
                        },
                        room=self.game_round.game_id,
                    )

                send_make_decision_to_starter_game_player.apply_async(
                    args=[seats, 0, str(self.game_round.id), self.game_round.game_id],
                    countdown=settings.ACCEPT_INSURANCE_SECONDS
                    if insurable_seats
                    else 0,
                    max_retries=5,
                )
            else:
                starter_game_player = await self.get_starter_game_player(seats, 0)

                data, hand = Hand.generate_data(
                    starter_game_player["cards"], starter_game_player["last_action"]
                )
                data_with_possible_actions = check_if_player_can_double_or_split(
                    starter_game_player["deposit"], starter_game_player["bet"], data
                )
                await external_sio.emit(
                    "make_decision",
                    data_with_possible_actions,
                    room=starter_game_player["sid"],
                )
                await external_sio.emit(
                    "decision_maker",
                    {
                        "seat_number": starter_game_player["seat_number"],
                        "decision_timer": starter_game_player["decision_time"]
                        - get_timestamp(),
                    },
                    room=starter_game_player["game_id"],
                )
        except IndexError:
            scan_result, data, game_id = await self.all_player_burst_or_have_bj()
            if scan_result is not None:
                await external_sio.emit(scan_result, data, room=game_id)
        finally:
            self.game_round.finished_dealing = True
            await self.game_round.save()

    async def _save_player_card(self, seats) -> None:
        game_player = await GamePlayer.get_motor_collection().find_one_and_update(
            {
                "game_round": self.round_id,
                "seat_number": seats[self.game_round.card_count],
                "bet": {"$gt": 0},
            },
            {"$push": {"cards": self.card}},
            return_document=True,
        )
        await PaymentManager.evaluate_bet_perfect_pair(game_player)
        await PaymentManager.evaluate_bet_21_3(game_player, self.game_round)
        await self.send_hand_value_to_room(game_player)

    async def _save_dealer_card(self) -> None:
        if len(self.game_round.dealer_cards) == 0:
            self.game_round.dealer_cards.append(self.card)
            self.game_round.card_count = 0
            await self.game_round.save()
            hand = Hand([self.card])
            await external_sio.emit(
                "dealer_score",
                {"score": hand.get_score_repr(), "cards": [self.card]},
                room=self.game_id,
            )
        else:
            raise ValidationError("Dealer already has one card")

    async def update_card_count(self) -> None:
        self.game_round.card_count += 1
        await self.game_round.save()

    async def send_hand_value_to_room(self, game_player: dict) -> None:
        hand = Hand(game_player["cards"])
        data = {
            "seat_number": game_player["seat_number"],
            "score": hand.get_score_repr(),
            "card": self.card,
        }
        await external_sio.emit("send_hand_value", data, room=game_player["game_id"])

    async def get_starter_game_player(
        self, seats: list, seat_number_index: int
    ) -> dict:
        game_player: GamePlayer = await GamePlayer.find_one(
            {
                "game_round": self.round_id,
                "seat_number": seats[seat_number_index],
                "bet": {"$gt": 0},
            }
        )
        can_continue_game = Hand(game_player.cards).can_continue_game()
        await self.check_player_activity(game_player, can_continue_game)
        if can_continue_game:
            starter_game_player = (
                await GamePlayer.get_motor_collection().find_one_and_update(
                    {
                        "game_round": self.round_id,
                        "seat_number": seats[seat_number_index],
                        "bet": {"$gt": 0},
                    },
                    {
                        "$set": {
                            "decision_time": get_timestamp(15),
                            "player_turn": True,
                            "making_decision": True,
                        }
                    },
                    return_document=True,
                )
            )
            return starter_game_player
        return await self.get_starter_game_player(seats, seat_number_index + 1)

    async def get_insurable_seats(self):
        insurable_seats = []
        game_players = (
            await GamePlayer.get_motor_collection()
            .find({"game_round": self.round_id})
            .to_list(length=7)
        )
        for game_player in game_players:
            data, _ = Hand.generate_data(
                game_player["cards"], game_player["last_action"]
            )
            if data["score"] != 21:
                insurable_seats.append(game_player["seat_number"])
        return insurable_seats


class AmericanCardsManager(BaseCardManager):
    def __init__(self, session_data: dict, round_id: str):
        super().__init__(session_data, round_id)
        self.card: Optional[str] = None
        self.game_round: Optional[GameRound] = None

    async def handle_card_dealing(self, card):
        self.check_card(card)
        self.card = card
        seats = await redis_cache.get_or_cache_game_player_seats(self.round_id)
        self.game_round: GameRound = await GameRound.get(
            PydanticObjectId(self.round_id)
        )
        self.check_can_scan_card()
        if len(self.game_round.dealer_cards) == 1 and self.game_round.card_count == len(
            seats
        ):
            await self.update_card_count()
            await self._save_second_dealer_card(seats)
            return
        elif len(seats) > self.game_round.card_count:
            await self._save_player_card(seats)
            await self.update_card_count()
            return
        await self._save_dealer_card()

    def check_can_scan_card(self) -> None:
        if int(self.game_round.start_timestamp) > get_timestamp():
            raise ValidationError("Betting time is not over")
        elif (
            self.game_round.insurance_timestamp
            and int(self.game_round.insurance_timestamp) > get_timestamp()
        ):
            raise ValidationError("Insurance decision time is not over")

    async def _save_second_dealer_card(self, seats):
        await self._save_dealer_card()
        dealer_hand = Hand(self.game_round.dealer_cards)
        game_round_dict = json.loads(self.game_round.json())
        game_round_dict["_id"] = game_round_dict["id"]
        try:
            if (
                dealer_hand.get_score_repr() == "BJ"
                and "A" not in self.game_round.dealer_cards[0]
            ):
                payment_manager = PaymentManager(self.game_id, game_round_dict)
                await payment_manager.pay_winnings()
            elif self.game_round.dealer_cards[0][1] == "A":
                insurable_seats = await self.get_insurable_seats()
                if insurable_seats:
                    self.game_round.insurance_timestamp = get_timestamp(
                        settings.ACCEPT_INSURANCE_SECONDS - 1
                    )
                    await self.game_round.save()
                    await external_sio.emit(
                        "make_insurance",
                        {
                            "decision_time": settings.ACCEPT_INSURANCE_SECONDS - 1,
                            "insurable_seats": insurable_seats,
                        },
                        room=self.game_round.game_id,
                    )

                if dealer_hand.get_score_repr() == "BJ":
                    payment_manager = PaymentManager(self.game_id, game_round_dict)
                    if insurable_seats:
                        await payment_manager.pay_winnings_after_insurance()
                    else:
                        await payment_manager.pay_winnings()
                else:
                    send_make_decision_to_starter_game_player.apply_async(
                        args=[
                            seats,
                            0,
                            str(self.game_round.id),
                            self.game_round.game_id,
                        ],
                        countdown=settings.ACCEPT_INSURANCE_SECONDS
                        if insurable_seats
                        else 0,
                        max_retries=5,
                    )
            else:
                starter_game_player = await self.get_starter_game_player(seats, 0)
                data, hand = Hand.generate_data(
                    starter_game_player["cards"], starter_game_player["last_action"]
                )

                await external_sio.emit(
                    "make_decision", data, room=starter_game_player["sid"]
                )
                await external_sio.emit(
                    "decision_maker",
                    {
                        "seat_number": starter_game_player["seat_number"],
                        "decision_timer": starter_game_player["decision_time"]
                        - get_timestamp(),
                    },
                    room=starter_game_player["game_id"],
                )
        except IndexError:
            scan_result, data, game_id = await self.all_player_burst_or_have_bj()
            if scan_result is not None:
                await external_sio.emit(scan_result, data, room=game_id)
        finally:
            await GameRound.get_motor_collection().find_one_and_update(
                {"_id": ObjectId(self.game_round.id)},
                {"$set": {"finished_dealing": True}},
            )

    async def _save_player_card(self, seats) -> None:
        game_player = await GamePlayer.get_motor_collection().find_one_and_update(
            {
                "game_round": self.round_id,
                "seat_number": seats[self.game_round.card_count],
                "bet": {"$gt": 0},
            },
            {"$push": {"cards": self.card}},
            return_document=True,
        )
        await PaymentManager.evaluate_bet_perfect_pair(game_player)
        await PaymentManager.evaluate_bet_21_3(game_player, self.game_round)
        await self.send_hand_value_to_room(game_player)

    async def _save_dealer_card(self) -> None:
        if len(self.game_round.dealer_cards) < 2:
            self.game_round.dealer_cards.append(self.card)
            self.game_round.card_count = 0
            await self.game_round.save()
            hand = Hand(self.game_round.dealer_cards[:1])
            await external_sio.emit(
                "dealer_score",
                {
                    "score": hand.get_score_repr(),
                    "cards": self.game_round.dealer_cards[:1],
                },
                room=self.game_id,
            )
        else:
            raise ValidationError("Dealer already has two cards")

    async def update_card_count(self) -> None:
        self.game_round.card_count += 1
        await self.game_round.save()

    async def send_hand_value_to_room(self, game_player: dict) -> None:
        hand = Hand(game_player["cards"])
        data = {
            "seat_number": game_player["seat_number"],
            "score": hand.get_score_repr(),
            "card": self.card,
        }
        await external_sio.emit("send_hand_value", data, room=game_player["game_id"])

    async def get_starter_game_player(
        self, seats: list, seat_number_index: int
    ) -> dict:
        game_player: GamePlayer = await GamePlayer.find_one(
            {
                "game_round": self.round_id,
                "seat_number": seats[seat_number_index],
                "bet": {"$gt": 0},
            }
        )
        can_continue_game = Hand(game_player.cards).can_continue_game()
        await self.check_player_activity(game_player, can_continue_game)
        if can_continue_game:
            starter_game_player = (
                await GamePlayer.get_motor_collection().find_one_and_update(
                    {
                        "game_round": self.round_id,
                        "seat_number": seats[seat_number_index],
                        "bet": {"$gt": 0},
                    },
                    {
                        "$set": {
                            "decision_time": get_timestamp(15),
                            "player_turn": True,
                            "making_decision": True,
                        }
                    },
                    return_document=True,
                )
            )
            return starter_game_player
        return await self.get_starter_game_player(seats, seat_number_index + 1)

    async def get_insurable_seats(self):
        insurable_seats = []
        game_players = (
            await GamePlayer.get_motor_collection()
            .find({"game_round": self.round_id})
            .to_list(length=7)
        )
        for game_player in game_players:
            data, _ = Hand.generate_data(
                game_player["cards"], game_player["last_action"]
            )
            if data["score"] != 21:
                insurable_seats.append(game_player["seat_number"])
        return insurable_seats
