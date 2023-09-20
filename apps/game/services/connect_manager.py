from typing import Optional, Tuple, List

from apps.connections import redis_cache
from apps.game.documents import GamePlayer
from apps.game.services.core_bridge import validate_user_token
from apps.game.services.custom_exception import ValidationError
from apps.game.cards.hand import Hand
from apps.game.services.utils import (
    get_game_round,
    get_time_left_in_seconds,
    get_game_state,
    get_game_state_for_dealer,
    generate_token_for_stream,
    check_if_player_can_double_or_split,
)


class BaseConnectManager:
    def __init__(self, game_id: str, sid: str):
        self.game_id = game_id
        self.sid = sid
        self.game_round: Optional[dict] = None

    async def connect_to_game(self) -> Tuple[dict, str]:
        raise NotImplementedError

    async def generate_on_connect_send_data(self, user_data: dict):
        raise NotImplementedError

    async def generate_base_connect_data(self):
        game_data = await redis_cache.get_or_cache_game(self.game_id)
        self.game_round = await get_game_round(self.game_id)
        dealer_cards = self.game_round.get("dealer_cards", [])[:1]
        if self.game_round["show_dealer_cards"]:
            dealer_cards = self.game_round.get("dealer_cards", [])
        hand = Hand(dealer_cards)
        return {
            "starts_at": get_time_left_in_seconds(
                self.game_round.get("start_timestamp")
            ),
            "insurance_timer": get_time_left_in_seconds(
                self.game_round.get("insurance_timestamp")
            ),
            "card_count": self.game_round.get("card_count", 0),
            "dealer_cards": dealer_cards,
            "dealer_score": hand.get_score_repr(),
            "round_id": self.game_round.get("round_id", None),
            "_round_id": str(self.game_round.get("_id", None)),
            "table_stream_key_1": game_data["table_stream_key_1"],
            "table_stream_key_2": game_data["table_stream_key_2"],
            "game_name": game_data["name"],
            "dealer_name": await redis_cache.get(f"{self.game_id}:dealer_name"),
            "game_state": get_game_state(self.game_round),
            "player_count": await redis_cache.get(f"{self.game_id}:player_count"),
            "stream_authorization": await generate_token_for_stream(self.game_id),
        }

    async def get_round_game_players_data(
        self, user_id: str, merchant_id: str
    ) -> Tuple[dict, dict, int]:
        seats = {}
        chips = {}
        total_bet = 0
        game_players: List[GamePlayer] = (
            await GamePlayer.find(GamePlayer.game_round == str(self.game_round["_id"]))
            .sort("seat_number")
            .to_list()
        )
        for game_player in game_players:
            seats[int(game_player.seat_number)] = {
                "cards": game_player.cards,
                "score": Hand(
                    game_player.cards, game_player.last_action
                ).get_score_repr(),
                "user_name": game_player.user_name,
                "making_decision": game_player.making_decision,
                "player_turn": game_player.player_turn,
                "decision_time": get_time_left_in_seconds(game_player.decision_time),
                "current_player": True
                if str(user_id) == game_player.user_id
                and merchant_id == str(game_player.merchant)
                else False,
                "last_action": "split"
                if game_player.last_action == "split:1"
                or game_player.last_action == "split:2"
                else game_player.last_action,
                "player_id": game_player.player_id,
                "insured": game_player.insured,
            }
            if game_player.user_id == str(user_id):

                total_bet += (
                    sum(game_player.bet_list)
                    + sum(game_player.bet_21_3_list)
                    + sum(game_player.bet_perfect_pair_list)
                )
            if game_player.making_decision:
                hand = Hand(game_player.cards, game_player.last_action)
                possible_actions = hand.get_possible_player_actions()
                possible_actions_dict = check_if_player_can_double_or_split(
                    game_player.deposit, game_player.bet, {"actions": possible_actions}
                )
                seats[int(game_player.seat_number)]["actions"] = possible_actions_dict[
                    "actions"
                ]

            chips[int(game_player.seat_number)] = [
                {
                    "type": "bet",
                    "bet_list": game_player.bet_list,
                    "total_bet": game_player.bet,
                },
                {
                    "type": "bet_21_3",
                    "bet_list": game_player.bet_21_3_list,
                    "total_bet": game_player.bet_21_3,
                },
                {
                    "type": "bet_perfect_pair",
                    "bet_list": game_player.bet_perfect_pair_list,
                    "total_bet": game_player.bet_perfect_pair,
                },
            ]
        taken_seats = await redis_cache.get_taken_seats(self.game_id)
        return {**taken_seats, **seats}, chips, total_bet


class ConnectManager(BaseConnectManager):
    def __init__(self, game_id: str, user_token: str, sid: str):
        super().__init__(game_id, sid)
        self.user_token = user_token
        self.merchant_id: Optional[str] = None
        self.game_players: Optional[List[dict]] = None
        self.merchant_data: Optional[dict] = None
        self.repeat_data: Optional[dict] = None
        self.user_balance: Optional[float] = None
        self.history = []
        self.dealer_name: Optional[str] = None
        self.base_data: Optional[dict] = None

    async def connect_to_game(self) -> Tuple[dict, str]:
        user_data = await self._check_if_user_can_connect()
        self.base_data = await super().generate_base_connect_data()
        self.game_players = await self._update_game_player_if_exists(user_data)
        self.history = await self.get_last_ten_gameplay_history(user_data)
        self.repeat_data = await redis_cache.get(
            f"{user_data['user_id']}:{self.merchant_id}:{str(self.game_round['prev_round_id'])}"
        )
        await redis_cache.redis_cache.hset(
            self.sid,
            mapping={
                "user_name": user_data["user_name"],
                "game_id": self.game_id,
                "user_token": self.user_token,
                "merchant_id": self.merchant_id,
                "user_id": user_data["user_id"],
                "player_id": str(user_data["user_id"]) + str(self.merchant_id),
            },
        )
        await redis_cache.redis_cache.incr(f"{self.game_id}:player_count")
        return await self.generate_on_connect_send_data(user_data), self.merchant_id

    async def _check_if_user_can_connect(self) -> dict:  # pragma: no cover
        if merchant_id := await redis_cache.get(self.user_token):
            self.merchant_id = merchant_id
            self.merchant_data = await redis_cache.get_or_cache_merchant(
                merchant_id, self.game_id
            )
            return await validate_user_token(self.user_token, self.merchant_data)
        raise ValidationError("Can not identify user please try again")

    async def _update_game_player_if_exists(self, user_data: dict) -> None:
        await GamePlayer.get_motor_collection().update_many(
            {
                "game_round": str(self.game_round["_id"]),
                "game_id": self.game_id,
                "user_id": str(user_data["user_id"]),
                "merchant": self.merchant_id,
                "archived": False,
            },
            {
                "$set": {
                    "user_token": self.user_token,
                    "sid": self.sid,
                    "is_active": True,
                }
            },
        )
        return (
            await GamePlayer.get_motor_collection()
            .find(
                {
                    "game_round": str(self.game_round["_id"]),
                    "game_id": self.game_id,
                    "user_id": str(user_data["user_id"]),
                    "merchant": self.merchant_id,
                    "archived": False,
                }
            )
            .to_list(7)
        )

    async def generate_on_connect_send_data(self, user_data):
        await self.get_user_balance(user_data)
        data = self.generate_default_send_data(user_data)
        seats, chips, total_bet = await self.get_round_game_players_data(
            user_data["user_id"], self.merchant_id
        )
        data["seats"] = seats
        data["chips"] = chips
        data["total_bet"] = total_bet
        data["insurable_seats"] = (
            await self.get_insurable_seats() if data["insurance_timer"] else []
        )
        return data

    async def get_user_balance(self, user_data):
        if self.game_players:
            self.user_balance = await redis_cache.get(
                f"{user_data['user_id']}:{self.merchant_id}"
            )
        else:
            await redis_cache.set_user_balance_in_cache(
                user_data["user_id"], self.merchant_id, user_data["total_balance"]
            )
            self.user_balance = user_data["total_balance"]

    def generate_default_send_data(self, user_data):
        return {
            "total_bet": 0,
            "dealer_name": self.dealer_name,
            "user_deposit": float(self.user_balance),
            "min_bet": self.merchant_data["min_bet"],
            "max_bet": self.merchant_data["max_bet"],
            "bet_range": self.merchant_data["bet_range"],
            "game_name": self.merchant_data["game_name"],
            "user_name": user_data["user_name"],
            "player_id": str(user_data["user_id"]) + str(self.merchant_id),
            "user_id": user_data["user_id"],
            "game_history": self.history,
            "can_make_repeat": True if self.repeat_data else False,
            **self.base_data,
        }

    async def get_last_ten_gameplay_history(self, user_data):
        return (
            await GamePlayer.get_motor_collection()
            .aggregate(
                [
                    {
                        "$match": {
                            "game_id": self.game_id,
                            "archived": True,
                            "player_id": str(user_data["user_id"])
                            + str(self.merchant_id),
                        }
                    },
                    {"$set": {"round_object_id": {"$toObjectId": "$game_round"}}},
                    {
                        "$lookup": {
                            "from": "GameRound",
                            "localField": "round_object_id",
                            "foreignField": "_id",
                            "as": "game_round",
                            "pipeline": [{"$match": {"finished": True}}],
                        }
                    },
                    {"$match": {"game_round": {"$not": {"$size": 0}}}},
                    {"$set": {"game_round": {"$first": "$game_round"}}},
                    {"$unset": ["game_round._id", "_id"]},
                    {
                        "$project": {
                            "action_list": 1,
                            "cards": 1,
                            "game_round.created_at": 1,
                            "game_round.dealer_name": 1,
                            "game_round.dealer_cards": 1,
                            "game_round.round_id": 1,
                            "game_round.was_reset": 1,
                            "game_round.winner": 1,
                            "insured": 1,
                            "join_game_at": 1,
                            "seat_number": 1,
                            "total_bet": 1,
                            "bet": 1,
                            "bet_21_3": 1,
                            "bet_21_3_combination": 1,
                            "bet_perfect_pair_combination": 1,
                            "bet_perfect_pair": 1,
                            "user_name": 1,
                            "winning_amount": 1,
                        }
                    },
                    {"$sort": {"game_round.created_at": -1}},
                ]
            )
            .to_list(length=10)
        )

    async def get_insurable_seats(self):
        insurable_seats = []
        game_players = (
            await GamePlayer.get_motor_collection()
            .find({"game_round": self.base_data.get("_round_id")})
            .to_list(length=7)
        )
        for game_player in game_players:
            data, _ = Hand.generate_data(
                game_player["cards"], game_player["last_action"]
            )
            if data["score"] != 21:
                insurable_seats.append(game_player["seat_number"])
        return insurable_seats


class DealerConnectManager(BaseConnectManager):
    def __init__(self, game_id: str, sid: str, jwt_token: str):
        super().__init__(game_id, sid)
        self.jwt_token = jwt_token

    async def connect_to_game(self) -> Tuple[dict, str]:
        # check_jwt_token(self.jwt_token)
        await redis_cache.redis_cache.hset(
            self.sid,
            mapping={"game_id": self.game_id, "user_id": "", "merchant_id": ""},
        )
        return await self.generate_on_connect_send_data({}), self.sid

    async def generate_on_connect_send_data(self, user_data: dict) -> dict:
        await redis_cache.redis_cache.incr(f"{self.game_id}:player_count")
        data = await self.generate_base_connect_data()
        seats, chips, _ = await self.get_round_game_players_data("1", "random_str")
        data["game_state"] = get_game_state_for_dealer(self.game_round, seats)
        data["seats"] = seats
        data["chips"] = chips
        data["finished_dealing"] = self.game_round["finished_dealing"]
        return data
