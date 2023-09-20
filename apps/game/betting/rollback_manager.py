from typing import Optional

from apps.connections import redis_cache
from apps.game.documents import GamePlayer
from apps.game.services.custom_exception import ValidationError
from apps.game.services.utils import get_timestamp
from apps.game.managers.base_game_manager import BaseGameManager


class RollbackManger(BaseGameManager):
    def __init__(self, user_session_data: dict, sid: str, rollback_type: str):
        super().__init__(user_session_data)
        self.sid = sid
        self.rollback_type = rollback_type
        self.game_player: Optional[dict] = None
        self.game_round: Optional[dict] = None

    async def make_rollback(self, seat_number: int, rollback_type: str = "bet"):
        self.game_player = await self.get_game_player(seat_number)
        self.game_round = await self.get_game_round()
        self.rollback_type = rollback_type
        self.check_can_make_rollback()
        amount = self.game_player[f"{self.rollback_type}_list"][-1]
        user_balance = await redis_cache.get(
            f"{self.game_player['user_id']}:{self.game_player['merchant']}"
        )
        updated_game_player = (
            await GamePlayer.get_motor_collection().find_one_and_update(
                {"_id": self.game_player["_id"]},
                {
                    "$set": {
                        self.rollback_type: self.game_player[self.rollback_type]
                        - amount,
                        "total_bet": self.game_player["total_bet"] - amount,
                        "deposit": float(user_balance) + amount,
                        f"{self.rollback_type}_list": self.game_player[
                            f"{self.rollback_type}_list"
                        ][:-1],
                        "action_list": self.game_player["action_list"]
                        + [
                            {
                                "rollback": self.game_player[
                                    f"{self.rollback_type}_list"
                                ][-1]
                            }
                        ],
                    },
                },
                return_document=True,
            )
        )
        await redis_cache.set_user_balance_in_cache(
            self.game_player["user_id"],
            self.game_player["merchant"],
            float(updated_game_player["deposit"]),
        )
        await redis_cache.clean_no_bet_seat_after_rollback(
            updated_game_player["total_bet"],
            updated_game_player["game_round"],
            updated_game_player["seat_number"],
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
        return {
            "seat_number": seat_number,
            "rollback_type": self.rollback_type,
            "total_bet": updated_game_player["total_bet"],
            "bet": updated_game_player[self.rollback_type],
            "bet_list": updated_game_player[f"{self.rollback_type}_list"],
            "balance": updated_game_player["deposit"],
            "user_total_bet": list(user_total_bet)[0].get("user_total_bet"),
        }

    def check_can_make_rollback(self):
        if not self.game_player:
            raise ValidationError("Player has not placed any bet yet")
        if self.rollback_type not in ["bet", "bet_21_3", "bet_perfect_pair"]:
            raise ValidationError("Rollback type is unknown")
        if self.game_round["start_timestamp"] < get_timestamp():
            raise ValidationError("Rollback time is over")
        if len(self.game_player[f"{self.rollback_type}_list"]) == 0:
            raise ValidationError("There is no bet to rollback")
        if self.rollback_type == "bet":
            self.check_can_rollback_bet()

    def check_can_rollback_bet(self):
        if (
            self.game_player["bet_21_3"]
            > self.game_player["bet"] - self.game_player["bet_list"][-1]
        ):
            raise ValidationError("Side bet 21+3 can not be more than main bet")
        if (
            self.game_player["bet_perfect_pair"]
            > self.game_player["bet"] - self.game_player["bet_list"][-1]
        ):
            raise ValidationError("Side bet Perfect Pair can not be more than main bet")
