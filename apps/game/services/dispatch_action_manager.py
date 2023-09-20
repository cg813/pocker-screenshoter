from typing import Optional, Tuple

from bson import ObjectId
import socketio
from apps.config import settings
from apps.game.betting.betting_manager import BettingManager

from apps.game.documents import GamePlayer, GameRound
from apps.game.cards.actions_card_manager import ActionCardManager
from apps.game.services.custom_exception import ValidationError
from apps.game.services.utils import get_timestamp
from apps.game.cards.hand import Hand

external_sio = socketio.AsyncRedisManager(settings.WS_MESSAGE_QUEUE, write_only=True)


class DispatchActionManager:
    def __init__(
        self,
        session_data: dict,
        round_id: str,
        sid: str,
        action_type: str,
        seat_number: int = 0,
    ):
        self.session_data = session_data
        self.round_id = round_id
        self.seat_number = seat_number
        self.sid = sid
        self.action_type = action_type
        self.game_player: Optional[GamePlayer] = None

    async def make_action(self) -> Tuple:
        try:
            actions = {
                "hit": self.make_hit,
                "double": self.make_double,
                "stand": self.stand,
                "auto_stand": self.auto_stand,
                "split": self.split,
            }
            await self.get_player_and_validate_action()
            return await actions.get(self.action_type)()
        except AttributeError:
            raise ValidationError("Can not make Action")

    async def get_player_and_validate_action(self) -> None:
        try:
            self.game_player = await GamePlayer.find_one(
                {
                    "game_round": self.round_id,
                    "making_decision": True,
                    "player_turn": True,
                }
            )
            self.validate_action()
        except AttributeError:
            raise ValidationError("Can not find game player or it is not your turn")

    async def split(self):
        self.check_decision_timestamp()
        split_data = await BettingManager(
            self.session_data, self.game_player.sid, "split"
        ).make_split(self.game_player)
        await external_sio.emit(
            "player_action", split_data, room=self.game_player.game_id
        )

    async def stand(self):
        self.check_decision_timestamp()
        action_card_manager = ActionCardManager(self.session_data, self.round_id)
        data = {"seat_number": self.game_player.seat_number, "action_type": "stand"}
        await external_sio.emit("player_action", data, room=self.game_player.game_id)
        return await action_card_manager.stand(self.game_player)

    async def auto_stand(self):
        action_card_manager = ActionCardManager(self.session_data, self.round_id)
        data = {"seat_number": self.game_player.seat_number, "action_type": "stand"}
        await external_sio.emit("player_action", data, room=self.game_player.game_id)
        return await action_card_manager.stand(self.game_player)

    async def make_hit(self) -> Tuple[str, dict, str]:
        self.check_decision_timestamp()
        await GamePlayer.get_motor_collection().find_one_and_update(
            {"_id": ObjectId(str(self.game_player.id))},
            {
                "$set": {"last_action": "hit", "making_decision": False},
                "$push": {
                    "action_list": {
                        "hit": 0,
                        "decision_time": self.game_player.decision_time,
                        "action_time": get_timestamp(),
                    }
                },
            },
        )
        data = {"seat_number": self.game_player.seat_number, "action_type": "hit"}
        return "player_action", data, self.game_player.game_id

    async def make_double(self) -> None:
        self.game_player = await GamePlayer.find_one(
            {
                "game_round": self.round_id,
                "sid": self.sid,
                "making_decision": True,
                "player_turn": True,
            }
        )
        self.validate_action()
        self.check_decision_timestamp()
        self.validate_action_for_split_and_double()

        if update_game_player_data := await BettingManager.make_double(
            self.session_data, self.game_player
        ):
            await external_sio.emit(
                "update_game_player", update_game_player_data, room=self.game_player.sid
            )
            data = {
                "seat_number": self.game_player.seat_number,
                "action_type": "double",
            }
            await external_sio.emit(
                "player_action", data, room=self.game_player.game_id
            )

    async def make_insurance(self, value: bool) -> None:
        self.game_player = await GamePlayer.find_one(
            {
                "game_round": self.round_id,
                "seat_number": self.seat_number,
                "sid": self.sid,
            }
        )
        self.validate_action()
        await self.validate_action_for_insurance()
        data = {
            "seat_number": self.game_player.seat_number,
            "action_type": "insurance",
            "value": False,
        }
        if value is True:
            if update_game_player_data := await BettingManager.make_insurance(
                self.session_data, self.game_player, self.game_round
            ):
                await external_sio.emit(
                    "update_game_player",
                    update_game_player_data,
                    room=self.game_player.sid,
                )
                data["value"] = True
                await external_sio.emit(
                    "player_action", data, room=self.game_player.game_id
                )
        else:
            self.game_player.insured = False
            self.game_player.last_action = "insurance"
            await self.game_player.save()
            await external_sio.emit(
                "player_action", data, room=self.game_player.game_id
            )

    def check_decision_timestamp(self):
        if float(self.game_player.decision_time) <= float(get_timestamp()):
            raise ValidationError("Time for making decision is over")

    def validate_action(self):
        if self.sid != self.game_player.sid:
            raise ValidationError("Player is not allowed to make action")
        hand = Hand(self.game_player.cards)
        if not hand.can_continue_game():
            raise ValidationError("Can not make Action")

    def validate_action_for_split_and_double(self):
        if len(self.game_player.cards) > 2:
            raise ValidationError(f"Action {self.action_type} is not allowed")
        if float(self.game_player.deposit) < self.game_player.bet:
            raise ValidationError(f"Not enough fund to make {self.action_type}")

    async def validate_action_for_insurance(self):
        self.game_round: GameRound = await GameRound.find_one(
            {"_id": ObjectId(self.round_id)}
        )

        if len(self.game_player.cards) > 2:
            raise ValidationError("Action insurance is not allowed")
        if self.game_player.insured in [True, False]:
            raise ValidationError("Insurance decision is already made")
        if "A" not in self.game_round.dealer_cards[0]:
            raise ValidationError(
                "You can not make insurance when dealer's first card is not an Ace"
            )
        if float(self.game_round.insurance_timestamp) <= float(get_timestamp()):
            raise ValidationError("Time for making insurance is over")
        if float(self.game_player.deposit) < (self.game_player.bet / 2):
            raise ValidationError("Not enough fund to make insurance")
