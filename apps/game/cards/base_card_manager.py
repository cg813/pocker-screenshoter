import socketio

from typing import Optional, Dict, Tuple
from bson import ObjectId

from apps.config import settings
from apps.game.documents import GamePlayer, GameRound
from apps.game.services.utils import get_timestamp
from apps.connections import redis_cache
from apps.game.cards.deck import deck
from apps.game.services.custom_exception import ValidationError
from apps.game.tasks import wait_player
from apps.game.cards.hand import Hand
from apps.game.managers.base_game_manager import BaseGameManager
from apps.game.services.payment_manager import PaymentManager
from apps.game.services.utils import check_if_player_can_double_or_split


external_sio = socketio.AsyncRedisManager(settings.WS_MESSAGE_QUEUE, write_only=True)


class BaseCardManager(BaseGameManager):
    def __init__(self, session_data: dict, round_id: str):
        super().__init__(session_data)
        self.round_id = round_id
        self.game_id = session_data["game_id"]
        self.game_player: Optional[GamePlayer] = None
        self.next_game_player: Optional[GamePlayer] = None

    @staticmethod
    async def check_player_activity(
        game_player: GamePlayer, can_continue_game: bool
    ) -> bool:
        if game_player.is_active is False and can_continue_game is True:
            wait_player.apply_async(
                args=[
                    str(game_player.id),
                    game_player.game_id,
                    len(game_player.action_list),
                ],
                countdown=settings.ACCEPT_BETS_SECONDS - 1,
            )
            return True
        return False

    async def send_decision_maker_data(self):
        from apps.game.consumers import external_sio

        await external_sio.emit(
            "decision_maker",
            {
                "seat_number": self.next_game_player.seat_number,
                "decision_timer": int(self.next_game_player.decision_time)
                - get_timestamp(),
            },
            room=self.next_game_player.game_id,
        )

    async def move_to_next_player(self) -> Tuple[str, Dict, str]:
        try:
            self.next_game_player = await self.get_next_player()
            data, hand = Hand.generate_data(
                self.next_game_player.cards, self.next_game_player.last_action
            )
            can_continue_game = hand.can_continue_game()
            if await self.check_player_activity(
                self.next_game_player, can_continue_game
            ):
                await self.send_decision_maker_data()
                return "player_disconnect", {}, self.game_id
            data["seat_number"] = self.next_game_player.seat_number
            if not can_continue_game:
                await self.finish_player_turn(self.next_game_player, False)
                self.game_player = self.next_game_player
                await self.next_game_player.save()
                return await self.move_to_next_player()
            await self.send_decision_maker_data()
            data_check = check_if_player_can_double_or_split(
                self.next_game_player.deposit, self.next_game_player.bet, data
            )
            return "make_decision", data_check, self.next_game_player.sid
        except IndexError:
            scan_result, data, game_id = await self.all_player_burst_or_have_bj()
            return scan_result, data, game_id

    async def get_next_player(self) -> GamePlayer:
        seats = await redis_cache.get_or_cache_game_player_seats(self.round_id)
        seat_id = seats.index(self.game_player.seat_number)
        next_game_player: GamePlayer = await GamePlayer.find_one(
            {
                "seat_number": seats[seat_id + 1],
                "game_round": self.round_id,
                "bet": {"$gt": 0},
            }
        )
        next_game_player.making_decision = True
        next_game_player.player_turn = True
        next_game_player.decision_time = get_timestamp(15)
        await next_game_player.save()
        return next_game_player

    @staticmethod
    async def finish_player_turn(
        game_player: GamePlayer, making_decision: bool
    ) -> GamePlayer:
        game_player.making_decision = making_decision
        if making_decision is False:
            game_player.player_turn = False
            game_player.finished_turn = True
        else:
            game_player.decision_time = get_timestamp(15)
        await game_player.save()
        return game_player

    async def finish_dealing(self) -> None:
        """
        This func executes when last player finishes his/her turn.
        We finish game round and send event for dealer to scan last dealer card.
        """
        await GameRound.get_motor_collection().find_one_and_update(
            {"_id": ObjectId(self.round_id), "game_id": self.game_id},
            {"$set": {"finished_dealing": True}},
        )

    async def check_21(self, hand: Hand) -> bool:
        if hand.score == 21:
            await self.finish_player_turn(self.next_game_player, False)
            self.game_player = self.next_game_player
            await self.next_game_player.save()
            return True
        return False

    @staticmethod
    def check_card(card: str) -> None:
        if card not in deck:
            raise ValidationError("Incorrect card")

    async def all_player_burst_or_have_bj(self):
        await self.finish_dealing()
        seats = await redis_cache.get_or_cache_game_player_seats(self.round_id)
        more_21_score = 0
        bj_score = 0
        game_round = await GameRound.get_motor_collection().find_one_and_update(
            {"_id": ObjectId(self.round_id)},
            {"$set": {"show_dealer_cards": True}},
            return_document=True,
        )
        for seat in seats:
            game_player: GamePlayer = await GamePlayer.find_one(
                {"seat_number": seat, "game_round": self.round_id}
            )
            data, hand = Hand.generate_data(game_player.cards, game_player.last_action)
            score = data["score"]
            if score == 21 and len(game_player.cards) == 2:
                if game_player.last_action in ["split:1", "split:2"]:
                    score = 21
                else:
                    score = "BJ"
            if score != "BJ" and score > 21:
                more_21_score = more_21_score + 1

            if score == "BJ":
                bj_score = bj_score + 1

        dealer_hand = Hand(game_round["dealer_cards"])
        await external_sio.emit(
            "dealer_score",
            {
                "score": dealer_hand.get_score_repr(),
                "cards": game_round["dealer_cards"],
            },
            room=self.game_id,
        )
        if bj_score + more_21_score == len(seats) and (
            bj_score == 0
            or (
                bj_score > 0
                and (not game_round["dealer_cards"][0][1] in ["A", "T", "K", "Q", "J"])
            )
        ):
            payment_manager = PaymentManager(self.game_id, game_round)
            await payment_manager.pay_winnings()
            return "", {}, None
        elif Hand(game_round["dealer_cards"])._hand_scores.score >= 17:
            payment_manager = PaymentManager(self.game_id, game_round)
            await payment_manager.pay_winnings()
            return "", {}, None
        else:
            return "scan_dealer_card", {}, self.game_id
