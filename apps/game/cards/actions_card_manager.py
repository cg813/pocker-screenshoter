from typing import Optional, Tuple, Dict

import socketio
from bson import ObjectId

from apps.config import settings
from apps.game.documents import GamePlayer, GameRound
from apps.game.services.utils import get_timestamp, check_if_player_can_double_or_split
from apps.game.cards.hand import Hand
from apps.game.cards.base_card_manager import BaseCardManager
from apps.game.services.payment_manager import PaymentManager
from apps.game.services.custom_exception import ValidationError
from apps.connections import redis_cache

external_sio = socketio.AsyncRedisManager(settings.WS_MESSAGE_QUEUE, write_only=True)


class ActionCardManager(BaseCardManager):
    def __init__(self, session_data: dict, round_id: str):
        super().__init__(session_data, round_id)
        self.card: Optional[str] = None

    async def scan_card(self, card: str):
        self.check_card(card)
        actions = {
            "stand": self.stand,
            "hit": self.hit,
            "double": self.double,
            "split:1": self.scan_split_first_card,
            "split:2": self.scan_split_second_card,
        }

        self.card = card
        self.game_player: GamePlayer = await GamePlayer.find_one(
            {"game_id": self.game_id, "game_round": self.round_id, "player_turn": True}
        )
        await self.check_if_dealer_can_scan_player_card()
        return await actions[self.game_player.last_action]()

    async def scan_dealer_card(self, card: str):
        self.check_card(card)
        await self.check_if_dealer_can_scan_card()
        self.card = card
        game_round = await GameRound.get_motor_collection().find_one_and_update(
            {"_id": ObjectId(self.round_id), "game_id": self.game_id},
            {"$push": {"dealer_cards": self.card}},
            return_document=True,
        )
        hand = Hand(game_round["dealer_cards"])
        await external_sio.emit(
            "dealer_score",
            {"score": hand.get_score_repr(), "cards": game_round["dealer_cards"]},
            room=self.game_id,
        )
        if hand.dealer_action():
            scan_result, data, game_id = await self.check_dealer_cards(game_round)
            if scan_result:
                await external_sio.emit(scan_result, data, room=game_id)
        else:
            payment_manager = PaymentManager(self.game_id, game_round)
            await payment_manager.pay_winnings()
            # await self.finish_round()

    async def hit(self):
        self.game_player.cards.append(self.card)
        hand = Hand(self.game_player.cards)
        if can_continue_game := hand.can_continue_game():
            data = await self.save_player_card_and_send_evaluation(True)
            await super().check_player_activity(self.game_player, can_continue_game)
            return "make_decision", data, self.game_player.sid
        await self.save_player_card_and_send_evaluation(False)
        return await self.move_to_next_player()

    async def stand(self, game_player: GamePlayer):
        self.game_player = game_player
        self.game_player.last_action = "stand"
        self.game_player.action_list.append(
            {
                "stand": 0,
                "decision_time": game_player.decision_time,
                "action_time": get_timestamp(),
            }
        )
        await self.finish_player_turn(game_player, False)
        return await self.move_to_next_player()

    async def double(self):
        self.game_player.cards.append(self.card)
        await self.save_player_card_and_send_evaluation(False)
        return await self.move_to_next_player()

    async def scan_split_first_card(self):
        self.game_player.cards.append(self.card)
        self.game_player.last_action = "split:2"
        await self.game_player.save()
        hand = Hand(self.game_player.cards, last_action=self.game_player.last_action)
        data = {
            "seat_number": self.game_player.seat_number,
            "score": hand.get_score_repr(),
            "card": self.card,
        }
        return "send_hand_value", data, self.game_id

    async def scan_split_second_card(self):
        game_player: GamePlayer = await GamePlayer.find_one(
            {
                "game_id": self.game_id,
                "game_round": self.round_id,
                "seat_number": self.game_player.seat_number + 1,
            }
        )
        game_player.cards.append(self.card)
        await game_player.save()
        data_2, hand_2 = Hand.generate_data(game_player.cards, game_player.last_action)
        hand_data = {
            "seat_number": game_player.seat_number,
            "score": hand_2.get_score_repr(),
            "card": self.card,
        }
        await external_sio.emit("send_hand_value", hand_data, room=self.game_id)
        data_1, hand_1 = Hand.generate_data(
            self.game_player.cards, self.game_player.last_action
        )
        data_1 = check_if_player_can_double_or_split(
            self.game_player.deposit, self.game_player.bet, data_1
        )
        if can_continue_game := hand_1.can_continue_game():
            await GamePlayer.get_motor_collection().update_one(
                {"_id": ObjectId(str(self.game_player.id))},
                {"$set": {"decision_time": get_timestamp(15), "making_decision": True}},
            )
            await super().check_player_activity(self.game_player, can_continue_game)
            return "make_decision", data_1, self.game_player.sid
        await self.finish_player_turn(self.game_player, False)
        return await self.move_to_next_player()

    async def save_player_card_and_send_evaluation(self, making_decision: bool):
        evaluation, hand = Hand.generate_data(
            self.game_player.cards, self.game_player.last_action
        )
        self.game_player = await self.finish_player_turn(
            self.game_player, making_decision
        )
        data = {
            "seat_number": self.game_player.seat_number,
            "score": hand.get_score_repr(),
            "card": self.card,
        }
        await external_sio.emit("hand_value", data, room=self.game_id)
        return evaluation

    async def check_if_dealer_can_scan_card(self):
        game_round = await GameRound.find_one(
            {"_id": ObjectId(self.round_id), "game_id": self.game_id}
        )
        hand = Hand(game_round.dealer_cards)
        dealer_hand = hand._hand_scores.second_score
        if dealer_hand >= 17:
            raise ValidationError("Scanning dealer-card over 16 is not allowed")
        if game_round.finished is True:
            raise ValidationError("Round is Finished")

    async def check_if_dealer_can_scan_player_card(self):
        if self.game_player.making_decision is True:
            raise ValidationError("Can not scan card when player is making a decision")

    async def finish_round(self) -> None:
        """
        This func executes when dealer's last card will come out and scanning card is not allowed.
        We finish game round, update players with winnings and start new round.
        """
        await GameRound.get_motor_collection().find_one_and_update(
            {"_id": ObjectId(self.round_id), "game_id": self.game_id},
            {"$set": {"finished": True}},
        )

    async def check_dealer_cards(self, game_round) -> Tuple[str, Dict, str]:
        seats = await redis_cache.get_or_cache_game_player_seats(self.round_id)
        players_with_bj = 0
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
            if score == "BJ":
                players_with_bj = players_with_bj + 1
        if players_with_bj == len(seats):
            payment_manager = PaymentManager(self.game_id, game_round)
            await payment_manager.pay_winnings()
            # await GameRound.get_motor_collection().find_one_and_update(
            #     {"_id": ObjectId(self.round_id), "game_id": self.game_id},
            #     {"$set": {"finished": True}},
            # )
            return None, {}, None
        else:
            return "scan_dealer_card", {}, self.game_id
