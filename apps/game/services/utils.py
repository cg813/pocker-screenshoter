import calendar
import random
import secrets
import jwt
import functools

from typing import Callable
from beanie import PydanticObjectId
from datetime import datetime
from string import ascii_lowercase, ascii_uppercase, digits

from apps.game.services.custom_exception import ValidationError
from apps.game.cards.hand import Hand
from apps.config import settings


def generate_api_key(length: int = 80) -> secrets:
    """Generates api key for merchants.
    param length how many characters will have api key default is 80.
    """
    return secrets.token_urlsafe(length)


def get_timestamp(seconds: int = 0) -> int:
    return calendar.timegm(datetime.utcnow().utctimetuple()) + seconds
    # return datetime.datetime.utcnow().timestamp() + seconds


def get_game_state(game_round: dict) -> str:
    if (
        game_round["insurance_timestamp"]
        and int(game_round["insurance_timestamp"]) > get_timestamp()
    ):
        return "insurance"
    if (
        game_round["start_timestamp"]
        and int(game_round["start_timestamp"]) > get_timestamp()
    ):
        return "betting"
    if (
        game_round["start_timestamp"]
        and int(game_round["start_timestamp"]) <= get_timestamp()
    ):
        return "dealing"
    return "waiting"


def get_game_state_for_dealer(game_round: dict, seats: dict) -> str:
    if (
        game_round["insurance_timestamp"]
        and int(game_round["insurance_timestamp"]) > get_timestamp()
    ):
        return "insurance"
    if (
        game_round["start_timestamp"]
        and int(game_round["start_timestamp"]) > get_timestamp()
    ):
        return "betting"
    for _, player in seats.items():
        print(player)
        if player and player["player_turn"] and player["making_decision"]:
            return "waiting_player_decision"
        elif player and player["player_turn"] and not player["making_decision"]:
            return "waiting_dealer_scan_player_card"
    if (
        game_round["finished_dealing"]
        and Hand(game_round["dealer_cards"]).dealer_action()
    ):
        return "waiting_dealer_scan_dealer_card"
    if game_round["start_timestamp"] and not game_round["finished_dealing"]:
        return "dealing"
    return "waiting"


def get_time_left_in_seconds(timestamp: str) -> int:
    current_timestamp = get_timestamp()
    if timestamp and int(timestamp) > current_timestamp:
        return int(timestamp) - current_timestamp
    return 0


def id_generator():
    size = 6
    chars = ascii_lowercase + ascii_uppercase + digits
    return "".join(random.choice(chars) for _ in range(size))


async def get_game_round(game_id: str):
    from apps.game.documents import GameRound

    if game_round := await GameRound.get_motor_collection().find_one(
        {"game_id": game_id, "finished": False}
    ):
        return game_round
    raise ValidationError("No active round")


async def generate_token_for_stream(game_id: str):
    from apps.game.documents import Game

    game = await Game.get_motor_collection().find_one(
        {"_id": PydanticObjectId(game_id)}
    )

    payload_data = {
        "streamID": game["table_stream_key_1"],
        "type": "play",
        "exp": get_timestamp(300),
    }

    token = jwt.encode(payload_data, settings.SECRET_KEY, algorithm="HS256")

    return token


def check_jwt_token(token: str):
    try:
        jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.exceptions.InvalidTokenError:
        raise ValidationError("Invalid token")


def catch_error(func: Callable):
    from apps.game.consumers import sio

    @functools.wraps(func)
    async def decorator(sid, data, *args, **kwargs):
        try:
            await func(sid, data, *args, **kwargs)
        except ValidationError as error:
            await sio.emit("error", {"message": str(error)}, to=sid)

    return decorator


def check_should_not_move_to_next_game_player(
    game_player: dict, action_count_before_refresh: int
) -> bool:
    action_count_after_refresh = len(game_player["action_list"])
    if any(
        [
            # action after refresh - does not matter whether ia active or not
            action_count_after_refresh != action_count_before_refresh,
            # player finished turn and made action after refresh,
            game_player["finished_turn"]
            and action_count_after_refresh != action_count_before_refresh,
            # player finished turn and made card demanding action before refresh
            game_player["finished_turn"]
            and game_player["last_action"] in ["hit", "split:1", "split:2", "double"],
        ]
    ):
        return True


def check_if_player_can_double_or_split(deposit: float, bet: float, data: dict) -> dict:
    if float(deposit) < bet and "actions" in data.keys():
        if "double" in data["actions"]:
            data["actions"].remove("double")
        if "split" in data["actions"]:
            data["actions"].remove("split")
    return data


def check_cards_are_consecutive(ranks: list):
    ordered_ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]
    ranks.sort(key=ordered_ranks.index)
    if all(
        [
            ordered_ranks.index(ranks[1]) - ordered_ranks.index(ranks[0]) == 1,
            ordered_ranks.index(ranks[2]) - ordered_ranks.index(ranks[1]) == 1,
        ]
    ) or ranks == ["2", "3", "A"]:
        return True
