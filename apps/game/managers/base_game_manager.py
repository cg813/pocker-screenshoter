from typing import Dict
from apps.game.documents import GameRound, GamePlayer
from apps.game.services.custom_exception import ValidationError


class BaseGameManager:
    def __init__(self, user_session_data: dict):
        self.game_id: str = user_session_data["game_id"]
        self.user_id: str = user_session_data["user_id"]
        self.merchant_id: str = user_session_data["merchant_id"]
        self.user_session_data = user_session_data

    async def get_game_round(self) -> Dict:
        if game_round := await GameRound.get_motor_collection().find_one(
            {"game_id": self.game_id, "finished": False}
        ):
            return game_round
        raise ValidationError("No active round")

    async def _get_or_create_game_player(
        self,
        game_round_id: str,
        seat_number: int,
        sid: str,
        balance: float,
        cards=None,
        bet: float = 0,
        total_bet: float = 0,
        split_external_id: str = None,
    ) -> Dict:
        if cards is None:
            cards = []
        return await GamePlayer.get_motor_collection().find_one_and_update(
            {
                "user_id": self.user_id,
                "game_id": self.game_id,
                "merchant": self.merchant_id,
                "archived": False,
                "seat_number": seat_number,
            },
            {
                "$setOnInsert": {
                    "sid": sid,
                    "user_token": self.user_session_data["user_token"],
                    "user_id": self.user_id,
                    "player_id": self.user_session_data["player_id"],
                    "user_name": self.user_session_data["user_name"],
                    "game_id": self.game_id,
                    "game_round": game_round_id,
                    "merchant": self.merchant_id,
                    "bet": bet if bet > 0 else 0,
                    "bet_list": [bet] if bet > 0 else [],
                    "bet_21_3": 0,
                    "bet_21_3_list": [],
                    "bet_21_3_winning": 0,
                    "bet_21_3_combination": None,
                    "bet_perfect_pair": 0,
                    "bet_perfect_pair_list": [],
                    "bet_perfect_pair_winning": 0,
                    "bet_perfect_pair_combination": None,
                    "action_list": [{"split": bet}] if split_external_id else [],
                    "decision_time": "",
                    "deposit": balance,
                    "insured": None,
                    "total_bet": total_bet,
                    "archived": False,
                    "cards": cards,
                    "is_active": True,
                    "seat_number": seat_number,
                    "finished_turn": False,
                    "external_ids": {"split": split_external_id}
                    if split_external_id
                    else {},
                    "last_action": "split:2" if split_external_id else None,
                    "inactivity_check_time": 0,
                }
            },
            upsert=True,
            return_document=True,
        )

    async def get_game_player(self, seat_number: int) -> Dict:
        return await GamePlayer.get_motor_collection().find_one(
            {
                "user_id": self.user_id,
                "game_id": self.game_id,
                "merchant": self.merchant_id,
                "archived": False,
                "seat_number": seat_number,
            }
        )

    @staticmethod
    async def check_positive_amount(amount: float):
        if amount <= 0:
            raise ValidationError("Unsupported amount")
