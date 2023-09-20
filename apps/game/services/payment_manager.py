import json
import socketio

from uuid import uuid4

from bson import ObjectId

from apps.config import settings
from apps.game.documents import GamePlayer, Merchant, GameRound
from apps.game.services.custom_exception import ValidationError
from apps.game.tasks import (
    send_lose_event_and_game_player_history,
    send_winning_to_merchant_and_update_game_player,
    start_new_round,
    send_push_to_merchant_and_update_game_player,
    send_reset_to_merchant_and_update_game_player,
    pay_winnings,
)
from apps.game.services.utils import (
    check_cards_are_consecutive,
    get_time_left_in_seconds,
)
from apps.game.services.schema_generator import generate_reset_request_data
from apps.game.cards.hand import Hand
from apps.connections import redis_cache


external_sio = socketio.AsyncRedisManager(settings.WS_MESSAGE_QUEUE, write_only=True)


class PaymentManager:
    def __init__(
        self,
        game_id: str,
        game_round: dict,
    ):
        self.game_id = game_id
        self.game_round = game_round

    async def pay_winnings(self):
        await GameRound.get_motor_collection().find_one_and_update(
            {"_id": ObjectId(self.game_round["_id"])},
            {"$set": {"show_dealer_cards": True}},
        )
        dealer_hand = Hand(self.game_round["dealer_cards"])

        await external_sio.emit(
            "dealer_score",
            {
                "score": dealer_hand.get_score_repr(),
                "cards": self.game_round["dealer_cards"],
            },
            room=self.game_id,
        )
        taken_seats = {}
        await GamePlayer.get_motor_collection().update_many(
            {"game_round": str(self.game_round["_id"])}, {"$set": {"archived": True}}
        )
        dealer_hand = Hand(self.game_round["dealer_cards"])
        merchants = (
            await Merchant.get_motor_collection()
            .find(
                {"games.game_id": self.game_id},
                {"_id": 1, "win_url": 1, "schema_type": 1},
            )
            .to_list(1000)
        )

        round_data = {
            "dealer_cards": self.game_round["dealer_cards"],
            "finished": self.game_round["finished"],
            "created_at": self.game_round["created_at"],
            "dealer_name": self.game_round["dealer_name"],
            "round_id": self.game_round["round_id"],
            "was_reset": self.game_round["was_reset"],
            "winner": self.game_round["winner"],
        }
        total_winnings = {}
        for merchant in merchants:
            win_url = merchant["win_url"]
            schema_type = merchant["schema_type"]
            game_players = (
                await GamePlayer.get_motor_collection()
                .find(
                    {
                        "game_round": str(self.game_round["_id"]),
                        "merchant": str(merchant["_id"]),
                        "bet": {"$gt": 0},
                    }
                )
                .to_list(1000)
            )
            for game_player in game_players:
                game_player["_id"] = str(game_player["_id"])
                if game_player["seat_number"] % 2 == 1:
                    taken_seats[game_player["seat_number"]] = {
                        "user_name": game_player["user_name"],
                        "cards": [],
                        "decision_time": None,
                        "last_action": None,
                        "making_decision": False,
                        "player_turn": False,
                        "score": "0",
                        "player_id": game_player["player_id"],
                        "insured": None,
                    }
                win = self.get_player_winning(game_player, dealer_hand)
                total_winnings[game_player["sid"]] = (
                    total_winnings.get(game_player["sid"], 0) + win
                )
                self.send_to_merchant(
                    win, game_player, win_url, round_data, schema_type
                )
        for sid, win in total_winnings.items():
            await external_sio.emit("total_winning", {"amount": win}, room=sid)
        await redis_cache.set(f"{self.game_id}:taken_seats", json.dumps(taken_seats))
        start_new_round.apply_async(
            args=[self.game_id, str(self.game_round["_id"]), taken_seats],
            countdown=10,
            max_retries=5,
        )

    def send_to_merchant(
        self, win, game_player, win_url, round_data, schema_type, *args
    ):
        if win > game_player["bet"]:
            send_winning_to_merchant_and_update_game_player.apply_async(
                args=[game_player, win_url, win, round_data, schema_type],
                max_retries=5,
            )
        elif win == game_player["bet"]:
            send_push_to_merchant_and_update_game_player.apply_async(
                args=[game_player, win_url, win, round_data, schema_type],
                max_retries=5,
            )
        else:
            send_lose_event_and_game_player_history.apply_async(
                args=[game_player, win_url, round_data, schema_type],
                max_retries=5,
            )

    async def pay_winnings_after_insurance(self):
        pay_winnings.apply_async(
            args=[self.game_id, self.game_round],
            countdown=settings.ACCEPT_INSURANCE_SECONDS,
            max_retries=5,
        )

    @staticmethod
    def get_player_winning(game_player: dict, dealer_hand: Hand):
        total_winning = 0
        player_hand = Hand(game_player["cards"], game_player["last_action"])

        if (
            player_hand.get_score_repr() == "BJ"
            and dealer_hand.get_score_repr() == "BJ"
        ):
            total_winning = game_player["bet"]
        elif (
            player_hand.get_score_repr() == "BJ"
            and dealer_hand.get_score_repr() != "BJ"
        ):
            total_winning = game_player["bet"] * 2.5
        elif game_player["insured"] and dealer_hand.get_score_repr() == "BJ":
            total_winning = game_player["bet"] * 1.5
        elif dealer_hand.get_score_repr() == "BJ" and player_hand.score <= 21:
            total_winning = 0
        elif dealer_hand.score < player_hand.score <= 21:
            total_winning = game_player["bet"] * 2
        elif player_hand.score == dealer_hand.score <= 21:
            total_winning = game_player["bet"]
        elif dealer_hand.score > 21 and player_hand.score <= 21:
            total_winning = game_player["bet"] * 2

        total_winning += game_player["bet_21_3_winning"]
        total_winning += game_player["bet_perfect_pair_winning"]

        return total_winning

    @staticmethod
    async def evaluate_bet_perfect_pair(game_player: dict):
        if game_player["bet_perfect_pair"] and len(game_player["cards"]) == 2:
            bet_perfect_pair_winning = 0
            bet_perfect_pair_combination = None
            ranks = [game_player["cards"][0][1], game_player["cards"][1][1]]
            suits = [game_player["cards"][0][2], game_player["cards"][1][2]]

            # PERFECT PAIR
            if len(set(ranks)) == 1 and len(set(suits)) == 1:
                bet_perfect_pair_winning = (
                    game_player["bet_perfect_pair"] * settings.PP_MULTIPLIER
                )
                bet_perfect_pair_combination = "PERFECT PAIR"
            # COLORED PAIR
            elif len(set(ranks)) == 1 and sorted(suits) in [["C", "S"], ["D", "H"]]:
                bet_perfect_pair_winning = (
                    game_player["bet_perfect_pair"] * settings.CP_MULTIPLIER
                )
                bet_perfect_pair_combination = "COLORED PAIR"
            # MIXED PAIR
            elif len(set(ranks)) == 1:
                bet_perfect_pair_winning = (
                    game_player["bet_perfect_pair"] * settings.MP_MULTIPLIER
                )
                bet_perfect_pair_combination = "MIXED PAIR"

            await GamePlayer.get_motor_collection().find_one_and_update(
                {"_id": ObjectId(game_player["_id"])},
                {
                    "$set": {
                        "bet_perfect_pair_winning": bet_perfect_pair_winning,
                        "bet_perfect_pair_combination": bet_perfect_pair_combination,
                    }
                },
            )

    @staticmethod
    async def evaluate_bet_21_3(game_player: dict, game_round: GameRound):
        if game_player["bet_21_3"] and len(game_player["cards"]) == 2:
            bet_21_3_winning = 0
            bet_21_3_combination = None
            cards = game_player["cards"][:2] + game_round.dealer_cards[:1]
            ranks = [cards[0][1], cards[1][1], cards[2][1]]
            suits = [cards[0][2], cards[1][2], cards[2][2]]

            # SUITED TRIPS
            if len(set(ranks)) == 1 and len(set(suits)) == 1:
                bet_21_3_winning = game_player["bet_21_3"] * settings.ST_MULTIPLIER
                bet_21_3_combination = "SUITED TRIPS"
            # STRAIGHT FLUSH
            elif len(set(suits)) == 1 and check_cards_are_consecutive(ranks):
                bet_21_3_winning = game_player["bet_21_3"] * settings.SF_MULTIPLIER
                bet_21_3_combination = "STRAIGHT FLUSH"
            # THREE OF A KIND
            elif len(set(ranks)) == 1:
                bet_21_3_winning = game_player["bet_21_3"] * settings.TK_MULTIPLIER
                bet_21_3_combination = "THREE OF A KIND"
            # STRAIGHT
            elif check_cards_are_consecutive(ranks):
                bet_21_3_winning = game_player["bet_21_3"] * settings.S_MULTIPLIER
                bet_21_3_combination = "STRAIGHT"
            # FLUSH
            elif len(set(suits)) == 1:
                bet_21_3_winning = game_player["bet_21_3"] * settings.F_MULTIPLIER
                bet_21_3_combination = "FLUSH"

            await GamePlayer.get_motor_collection().find_one_and_update(
                {"_id": ObjectId(game_player["_id"])},
                {
                    "$set": {
                        "bet_21_3_winning": bet_21_3_winning,
                        "bet_21_3_combination": bet_21_3_combination,
                    }
                },
            )


class ResetManager:
    def __init__(self, game_id: str, game_round: GameRound):
        self.game_id = game_id
        self.game_round = game_round
        self.taken_seats = {}

    async def reset(self):
        self._check_can_make_reset()

        await self.finish_round()
        merchants = await self.get_merchants()

        for merchant in merchants:
            rollback_url = merchant["rollback_url"]
            schema_type = merchant["schema_type"]
            game_players = (
                await GamePlayer.get_motor_collection()
                .find(
                    {
                        "merchant": str(merchant["_id"]),
                        "game_round": str(self.game_round.id),
                    }
                )
                .to_list(1000)
            )
            for game_player in game_players:
                self.update_taken_seats(game_player)
                cancel_list = self.generate_cancel_list(game_player)
                for bet_type, reset_bet_amount in cancel_list:
                    game_player["_id"] = str(game_player["_id"])
                    game_player["external_ids"][f"cancel_{bet_type}"] = str(uuid4())
                    send_data = generate_reset_request_data(
                        schema_type, reset_bet_amount, game_player, bet_type
                    )
                    send_reset_to_merchant_and_update_game_player.delay(
                        send_data, rollback_url, game_player, bet_type
                    )
                await self.archive_game_player(game_player)

        await redis_cache.set(
            f"{self.game_id}:taken_seats", json.dumps(self.taken_seats)
        )
        start_new_round.apply_async(
            args=[self.game_id, str(self.game_round.id), self.taken_seats],
            countdown=0,
            max_retries=5,
        )

    def _check_can_make_reset(self):
        if not self.game_round.start_timestamp:
            raise ValidationError("Game is reset already")
        elif get_time_left_in_seconds(self.game_round.start_timestamp) != 0:
            raise ValidationError("Can not reset the game before betting time is over")

    async def finish_round(self):
        self.game_round.finished = True
        self.game_round.was_reset = True
        await self.game_round.save()

    async def get_merchants(self):
        return (
            await Merchant.get_motor_collection()
            .find(
                {"games.game_id": self.game_id},
                {"_id": 1, "rollback_url": 1, "schema_type": 1},
            )
            .to_list(1000)
        )

    def update_taken_seats(self, game_player: dict):
        if game_player["seat_number"] % 2 == 1:
            self.taken_seats[game_player["seat_number"]] = {
                "user_name": game_player["user_name"],
                "cards": [],
                "decision_time": None,
                "last_action": None,
                "making_decision": False,
                "player_turn": False,
                "score": "0",
                "player_id": game_player["player_id"],
                "insured": None,
            }

    def generate_cancel_list(self, game_player: dict):
        cancel_list = []
        for bet_type in game_player["external_ids"]:
            reset_bet_amount = sum(
                [
                    (lambda bet: bet.get(bet_type, 0))(bet)
                    for bet in game_player["action_list"]
                ]
            )
            if bet_type == "bet":
                reset_bet_amount += sum(
                    [
                        (lambda bet: bet.get("repeat", 0))(bet)
                        for bet in game_player["action_list"]
                    ]
                ) - sum(
                    [
                        (lambda bet: bet.get("rollback", 0))(bet)
                        for bet in game_player["action_list"]
                    ]
                )
            cancel_list.append((bet_type, reset_bet_amount))
        return cancel_list

    async def archive_game_player(self, game_player):
        await GamePlayer.get_motor_collection().find_one_and_update(
            {"_id": ObjectId(game_player["_id"])},
            {
                "$set": {
                    "is_reset": True,
                    "archived": True,
                }
            },
        )
