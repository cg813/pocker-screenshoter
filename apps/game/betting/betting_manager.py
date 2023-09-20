import json
import socketio

from uuid import uuid4
from typing import Optional, Dict, Any

from apps.config import settings
from apps.connections import redis_cache
from apps.game.cards.hand import Hand
from apps.game.documents import GamePlayer, GameRound, Tip
from apps.game.services.custom_exception import ValidationError
from apps.game.services.schema_generator import (
    generate_bet_request_data,
    generate_tip_request_data,
)
from apps.game.services.core_bridge import send_data_to_merchant
from apps.game.services.utils import get_timestamp
from apps.game.tasks import send_bets_to_merchant, clean_all_seats_if_no_bets_are_placed
from apps.game.managers.base_game_manager import BaseGameManager

external_sio = socketio.AsyncRedisManager(settings.WS_MESSAGE_QUEUE, write_only=True)


class BettingManager(BaseGameManager):
    def __init__(self, user_session_data: dict, sid: str, bet_type: str):
        super().__init__(user_session_data)
        self.seat_number: Optional[int] = None
        self.sid = sid
        self.game_round: Optional[dict] = None
        self.game_player: Optional[dict] = None
        self.bet_type = bet_type
        self.amount: Optional[float] = None
        self.user_balance: Optional[float] = None
        self._merchant_min_ante: Optional[float] = None
        self._merchant_max_ante: Optional[float] = None

    async def charge_user(self, amount: float, seat_number: int, bet_type: str = "bet"):
        await self.check_positive_amount(amount)
        self.amount = amount
        self.seat_number = seat_number
        self.bet_type = bet_type
        self.game_round = await super().get_game_round()
        if self.bet_type == "bet":
            await redis_cache.take_seat(
                str(self.game_round["_id"]),
                self.seat_number,
                self.merchant_id,
                self.user_id,
                self.game_round["prev_round_id"],
            )

        self.user_balance = await redis_cache.get(f"{self.user_id}:{self.merchant_id}")
        self.check_bet_placement()
        self.game_player = await super()._get_or_create_game_player(
            game_round_id=str(self.game_round["_id"]),
            seat_number=self.seat_number,
            sid=self.sid,
            balance=self.user_balance,
        )
        await self._check_if_user_can_place_bet()
        return await self.update_game_player()

    @staticmethod
    async def make_double(user_session_data: dict, game_player: GamePlayer):
        double_external_id = str(uuid4())
        merchant = await redis_cache.get_or_cache_merchant(
            game_player.merchant, game_player.game_id
        )
        amount = game_player.bet
        send_data = generate_bet_request_data(
            merchant["schema_type"],
            amount,
            json.loads(game_player.json()),
            double_external_id,
        )
        status_code, data = await send_data_to_merchant(merchant["bet_url"], send_data)
        if status_code == 200 and data["status"].lower() == "ok":
            updated_game_player = (
                await GamePlayer.get_motor_collection().find_one_and_update(
                    {"_id": game_player.id},
                    {
                        "$set": {
                            "total_bet": game_player.total_bet + amount,
                            "deposit": float(data["total_balance"]),
                            "bet": game_player.bet + amount,
                            "bet_list": game_player.bet_list + [amount],
                            "action_list": game_player.action_list
                            + [
                                {
                                    "double": amount,
                                    "decision_time": game_player.decision_time,
                                    "action_time": get_timestamp(),
                                }
                            ],
                            "last_action": "double",
                            "making_decision": False,
                            "external_ids.double": double_external_id,
                        }
                    },
                    return_document=True,
                )
            )

            await redis_cache.set_user_balance_in_cache(
                user_session_data["user_id"],
                user_session_data["merchant_id"],
                float(updated_game_player["deposit"]),
            )
            user_total_bet = (
                await GamePlayer.get_motor_collection()
                .aggregate(
                    [
                        {
                            "$match": {
                                "player_id": updated_game_player["player_id"],
                                "game_round": updated_game_player["game_round"],
                            }
                        },
                        {
                            "$group": {
                                "_id": "$player_id",
                                "user_total_bet": {"$sum": "$total_bet"},
                            }
                        },
                    ]
                )
                .to_list(length=1)
            )
            update_game_player_data = {
                "seat_number": updated_game_player["seat_number"],
                "bet_list": updated_game_player["bet_list"],
                "bet": updated_game_player["bet"],
                "total_bet": sum(updated_game_player["bet_list"]),
                "user_deposit": updated_game_player["deposit"],
                "user_total_bet": list(user_total_bet)[0].get("user_total_bet"),
                "action": "double",
            }
            return update_game_player_data

    @staticmethod
    async def make_insurance(
        user_session_data: dict, game_player: GamePlayer, game_round: GameRound
    ):
        insurance_external_id = str(uuid4())
        merchant = await redis_cache.get_or_cache_merchant(
            game_player.merchant, game_player.game_id
        )
        amount = game_player.bet / 2
        send_data = generate_bet_request_data(
            merchant["schema_type"],
            amount,
            json.loads(game_player.json()),
            insurance_external_id,
        )
        status_code, data = await send_data_to_merchant(merchant["bet_url"], send_data)
        if status_code == 200 and data["status"].lower() == "ok":
            updated_game_player = (
                await GamePlayer.get_motor_collection().find_one_and_update(
                    {"_id": game_player.id},
                    {
                        "$set": {
                            "total_bet": game_player.total_bet + amount,
                            "deposit": float(data["total_balance"]),
                            "bet": game_player.bet,
                            "bet_list": game_player.bet_list + [amount],
                            "action_list": game_player.action_list
                            + [
                                {
                                    "insurance": amount,
                                    "decision_time": game_round.insurance_timestamp,
                                    "action_time": get_timestamp(),
                                }
                            ],
                            "last_action": "insurance",
                            "insured": True,
                            "external_ids.insurance": insurance_external_id,
                        }
                    },
                    return_document=True,
                )
            )
            await redis_cache.set_user_balance_in_cache(
                user_session_data["user_id"],
                user_session_data["merchant_id"],
                float(updated_game_player["deposit"]),
            )
            user_total_bet = (
                await GamePlayer.get_motor_collection()
                .aggregate(
                    [
                        {
                            "$match": {
                                "player_id": updated_game_player["player_id"],
                                "game_round": updated_game_player["game_round"],
                            }
                        },
                        {
                            "$group": {
                                "_id": "$player_id",
                                "user_total_bet": {"$sum": "$total_bet"},
                            }
                        },
                    ]
                )
                .to_list(length=1)
            )
            update_game_player_data = {
                "seat_number": updated_game_player["seat_number"],
                "bet_list": updated_game_player["bet_list"],
                "bet": updated_game_player["bet"],
                "total_bet": sum(updated_game_player["bet_list"]),
                "user_deposit": updated_game_player["deposit"],
                "user_total_bet": list(user_total_bet)[0].get("user_total_bet"),
                "action": "insurance",
            }
            return update_game_player_data
        elif status_code == 200 and data["status"].lower() != "ok":
            game_player.detail = "insufficient balance"
            game_player.insured = False
            await game_player.save()

            await external_sio.emit(
                "insufficient_balance",
                {
                    "message": "Not enough funds to place bet",
                    "balance": data["total_balance"],
                },
                room=game_player["sid"],
            )
            await redis_cache.set_user_balance_in_cache(
                user_session_data["user_id"],
                user_session_data["merchant_id"],
                float(game_player["deposit"]),
            )

    async def make_split(self, game_player: GamePlayer):
        split_external_id = str(uuid4())
        merchant = await redis_cache.get_or_cache_merchant(
            game_player.merchant, game_player.game_id
        )
        amount = game_player.bet
        send_data = generate_bet_request_data(
            merchant["schema_type"],
            amount,
            json.loads(game_player.json()),
            split_external_id,
        )
        status_code, data = await send_data_to_merchant(merchant["bet_url"], send_data)
        if status_code == 200 and data["status"].lower() == "ok":
            game_player_cards = game_player.cards
            game_player.cards = [game_player_cards[0]]
            game_player.last_action = "split:1"
            game_player.making_decision = False
            game_player.action_list.append(
                {
                    "split": 0,
                    "decision_time": game_player.decision_time,
                    "action_time": get_timestamp(),
                }
            )
            await game_player.save()
            splitted_game_player = await super()._get_or_create_game_player(
                game_round_id=game_player.game_round,
                seat_number=game_player.seat_number + 1,
                sid=game_player.sid,
                balance=float(data["total_balance"]),
                cards=[game_player_cards[1]],
                bet=amount,
                total_bet=amount,
                split_external_id=split_external_id,
            )
            await redis_cache.update_cached_seats(
                game_round_id=game_player.game_round,
                seat_number=game_player.seat_number,
            )
            await redis_cache.set_user_balance_in_cache(
                splitted_game_player["user_id"],
                splitted_game_player["merchant"],
                float(splitted_game_player["deposit"]),
            )
            user_total_bet = (
                await GamePlayer.get_motor_collection()
                .aggregate(
                    [
                        {
                            "$match": {
                                "player_id": splitted_game_player["player_id"],
                                "game_round": splitted_game_player["game_round"],
                            }
                        },
                        {
                            "$group": {
                                "_id": "$player_id",
                                "user_total_bet": {"$sum": "$total_bet"},
                            }
                        },
                    ]
                )
                .to_list(length=1)
            )

            split_data = {
                "seat_number": game_player.seat_number,
                game_player.seat_number: {
                    "cards": game_player.cards,
                    "score": Hand(
                        game_player.cards, last_action="split:1"
                    ).get_score_repr(),
                },
                splitted_game_player["seat_number"]: {
                    "cards": splitted_game_player["cards"],
                    "score": Hand(
                        splitted_game_player["cards"], last_action="split:2"
                    ).get_score_repr(),
                },
                "action_type": "split",
            }
            update_game_player_data = {
                "seat_number": game_player.seat_number,
                "bet_list": game_player.bet_list + splitted_game_player["bet_list"],
                "bet": splitted_game_player["bet"],
                "total_bet": sum(game_player.bet_list)
                + splitted_game_player["total_bet"],
                "user_deposit": splitted_game_player["deposit"],
                "user_total_bet": list(user_total_bet)[0].get("user_total_bet"),
                "action": "split",
            }
            await external_sio.emit(
                "update_game_player", update_game_player_data, room=game_player.sid
            )
            return split_data

    async def make_repeat(self, session_data: dict):
        self.game_round = await super().get_game_round()
        repeat_data = await redis_cache.get_repeat_data(
            f"{session_data['user_id']}:"
            f"{session_data['merchant_id']}:"
            f"{self.game_round['prev_round_id']}"
        )
        return_data = {}
        for seat in repeat_data:
            self.game_round = await super().get_game_round()
            self.user_balance = await redis_cache.get(
                f"{self.user_id}:{self.merchant_id}"
            )
            self.seat_number = int(seat)
            await redis_cache.take_seat(
                str(self.game_round["_id"]),
                self.seat_number,
                self.merchant_id,
                self.user_id,
                self.game_round["prev_round_id"],
            )
            self.check_bet_placement()
            self.game_player = await super()._get_or_create_game_player(
                game_round_id=str(self.game_round["_id"]),
                seat_number=int(seat),
                sid=self.sid,
                balance=self.user_balance,
            )
            self.check_if_can_make_repeat(repeat_data[seat]["bet"])
            return_data[seat] = await self.update_game_player_for_repeat(
                repeat_data[seat]
            )
            await external_sio.emit(
                "new_bet",
                {
                    "bet_type": "repeat",
                    "seat_number": seat,
                    "total_bet": return_data[seat]["total_bet"],
                    "bet": return_data[seat]["bet"],
                    "bet_list": return_data[seat]["bet_list"],
                    "bet_21_3": repeat_data[seat]["bet_21_3"],
                    "bet_21_3_list": repeat_data[seat]["bet_21_3_list"],
                    "bet_perfect_pair": repeat_data[seat]["bet_perfect_pair"],
                    "bet_perfect_pair_list": repeat_data[seat]["bet_perfect_pair_list"],
                    "user_name": self.user_session_data["user_name"],
                },
                room=self.user_session_data["game_id"],
                skip_sid=self.sid,
            )
        return return_data

    async def tip_dealer(self, amount: float, session_data: dict):
        await self.check_positive_amount(amount)
        game_round = await self.get_game_round()
        merchant = await redis_cache.get_or_cache_merchant(
            session_data["merchant_id"], game_round["game_id"]
        )
        external_id = str(uuid4())
        send_data = generate_tip_request_data(
            merchant["schema_type"],
            amount=amount,
            user_token=session_data["user_token"],
            external_id=external_id,
            game_id=game_round["game_id"],
            round_id=str(game_round["_id"]),
        )
        status_code, data = await send_data_to_merchant(merchant["bet_url"], send_data)
        if status_code == 200 and data["status"].lower() == "ok":
            await Tip(
                user_id=session_data["user_id"],
                merchant_id=session_data["merchant_id"],
                game_id=game_round["game_id"],
                round_id=str(game_round["_id"]),
                amount=amount,
                username=session_data["user_name"],
                external_id=external_id,
            ).create()

            await redis_cache.set_user_balance_in_cache(
                session_data["user_id"],
                session_data["merchant_id"],
                float(data["total_balance"]),
            )

            return {
                "player_id": f"{session_data['user_id']}{session_data['merchant_id']}",
                "user_deposit": data["total_balance"],
            }
        raise ValidationError("Can not tip the dealer")

    async def _check_if_user_can_place_bet(self) -> str:
        self.merchant_data = await redis_cache.get_or_cache_merchant(
            self.merchant_id, self.game_id
        )

        validators = {
            "bet": self.check_user_deposit,
            "bet_21_3": self.check_side_bet_placement,
            "bet_perfect_pair": self.check_side_bet_placement,
        }

        validators.get(self.bet_type)()
        return self.merchant_data["transaction_url"]

    async def update_game_player(self) -> Dict[str, Any]:
        self.game_player[f"{self.bet_type}_list"].append(self.amount)
        updated_game_player = (
            await GamePlayer.get_motor_collection().find_one_and_update(
                {"_id": self.game_player["_id"]},
                {
                    "$set": {
                        "total_bet": self.game_player["total_bet"] + self.amount,
                        "deposit": float(self.user_balance) - self.amount,
                        f"{self.bet_type}": self.game_player[f"{self.bet_type}"]
                        + self.amount,
                        f"{self.bet_type}_list": self.game_player[
                            f"{self.bet_type}_list"
                        ],
                        "action_list": self.game_player["action_list"]
                        + [
                            {
                                f"{self.bet_type}": self.game_player[
                                    f"{self.bet_type}_list"
                                ][-1],
                                "decision_time": self.game_round["start_timestamp"],
                                "action_time": get_timestamp(),
                            }
                        ],
                    }
                },
                return_document=True,
            )
        )
        await redis_cache.set_user_balance_in_cache(
            self.user_id,
            self.merchant_id,
            float(self.user_balance) - self.amount,
        )

        if self.game_round["start_timestamp"] is None:
            await GameRound.get_motor_collection().find_one_and_update(
                {"_id": self.game_round["_id"]},
                {"$set": {"start_timestamp": get_timestamp(15)}},
            )
            await external_sio.emit("start_timer", {"seconds": 15}, room=self.game_id)
            send_bets_to_merchant.apply_async(
                args=[str(self.game_round["_id"]), self.game_round["game_id"]],
                countdown=settings.ACCEPT_BETS_SECONDS,
                max_retries=5,
            )
            self.clean_seats()

        user_total_bet = (
            await GamePlayer.get_motor_collection()
            .aggregate(
                [
                    {
                        "$match": {
                            "player_id": updated_game_player["player_id"],
                            "game_round": updated_game_player["game_round"],
                        }
                    },
                    {
                        "$group": {
                            "_id": "$player_id",
                            "user_total_bet": {"$sum": "$total_bet"},
                        }
                    },
                ]
            )
            .to_list(length=1)
        )

        return {
            "bet_type": self.bet_type,
            "seat_number": self.seat_number,
            "total_bet": updated_game_player["total_bet"],
            self.bet_type: updated_game_player[self.bet_type],
            "user_deposit": updated_game_player["deposit"],
            f"{self.bet_type}_list": updated_game_player[f"{self.bet_type}_list"],
            "player_id": updated_game_player["player_id"],
            "user_total_bet": user_total_bet[0].get("user_total_bet", 0),
        }

    async def update_game_player_for_repeat(self, repeat_data):
        game_player = await GamePlayer.get_motor_collection().find_one_and_update(
            {"_id": self.game_player["_id"]},
            {
                "$set": {
                    "deposit": float(self.user_balance)
                    - (
                        float(repeat_data["bet"])
                        + float(repeat_data["bet_21_3"])
                        + float(repeat_data["bet_perfect_pair"])
                    ),
                    "bet": float(repeat_data["bet"]),
                    "bet_list": repeat_data["bet_list"],
                    "bet_21_3": float(repeat_data["bet_21_3"]),
                    "bet_21_3_list": repeat_data["bet_21_3_list"],
                    "bet_perfect_pair": float(repeat_data["bet_perfect_pair"]),
                    "bet_perfect_pair_list": repeat_data["bet_perfect_pair_list"],
                    "total_bet": repeat_data["bet"]
                    + repeat_data["bet_21_3"]
                    + repeat_data["bet_perfect_pair"],
                    "action_list": self.game_player["action_list"]
                    + [
                        {
                            "repeat": repeat_data["bet"]
                            + repeat_data["bet_21_3"]
                            + repeat_data["bet_perfect_pair"],
                            "decision_time": self.game_player["decision_time"],
                            "action_time": get_timestamp(),
                        }
                    ],
                }
            },
            return_document=True,
        )

        await redis_cache.set_user_balance_in_cache(
            self.user_id,
            self.merchant_id,
            float(self.user_balance) - float(repeat_data["bet"]),
        )
        if self.game_round["start_timestamp"] is None:
            await GameRound.get_motor_collection().find_one_and_update(
                {"_id": self.game_round["_id"]},
                {"$set": {"start_timestamp": get_timestamp(15)}},
            )
            await external_sio.emit("start_timer", {"seconds": 15}, room=self.game_id)
            send_bets_to_merchant.apply_async(
                args=[str(self.game_round["_id"]), self.game_round["game_id"]],
                countdown=settings.ACCEPT_BETS_SECONDS,
                max_retries=5,
            )
            self.clean_seats()
        return {
            "seat_number": game_player["seat_number"],
            "bet": game_player["bet"],
            "bet_list": game_player["bet_list"],
            "bet_21_3": game_player["bet_21_3"],
            "bet_21_3_list": repeat_data["bet_21_3_list"],
            "bet_perfect_pair": game_player["bet_perfect_pair"],
            "bet_perfect_pair_list": repeat_data["bet_perfect_pair_list"],
            "user_deposit": game_player["deposit"],
            "total_bet": game_player["total_bet"],
            "player_id": game_player["player_id"],
            "action_list": game_player["action_list"],
        }

    def clean_seats(self):
        clean_all_seats_if_no_bets_are_placed.apply_async(
            args=[str(self.game_round["_id"])], countdown=17, max_retries=5
        )

    def check_bet_placement(self):
        if self.bet_type not in ["bet", "bet_21_3", "bet_perfect_pair", "repeat"]:
            raise ValidationError("Bet type is unknown")
        if self.seat_number not in [1, 3, 5, 7, 9, 11, 13]:
            raise ValidationError("seat number out of range")
        if self.game_round["start_timestamp"] and get_timestamp() > float(
            self.game_round["start_timestamp"]
        ):
            raise ValidationError("betting time is over")

    def check_user_deposit(self):
        if self.merchant_data["max_bet"] < self.game_player["bet"] + self.amount:
            raise ValidationError("placing more than maximum bet is not allowed")
        if self.merchant_data["min_bet"] > self.game_player["bet"] + self.amount:
            raise ValidationError("placing less than minimum bet is not allowed")
        if float(self.user_balance) < self.amount:
            raise ValidationError("not enough funds")

    def check_side_bet_placement(self):
        if not self.game_player or self.game_player["bet"] == 0:
            raise ValidationError("Can not place side bet before placing main bet.")
        if self.game_player[self.bet_type] + self.amount > self.game_player["bet"]:
            raise ValidationError("Side bet can not be more than main bet")
        if self.game_player[self.bet_type] + self.amount > settings.MAX_SIDE_BET:
            raise ValidationError(
                "Placing mote than maximum side bet limit is not allowed"
            )

    def check_if_can_make_repeat(self, bet):
        if bet > float(self.user_balance):
            raise ValidationError("not enough funds to make repeat")
        elif self.game_player["bet"] == bet:
            raise ValidationError("Repeat is already made")
