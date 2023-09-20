import logging
from urllib.parse import parse_qs

import socketio
from beanie import PydanticObjectId

from apps.config import settings
from apps.connections import redis_cache
from apps.game.documents import GamePlayer, GameRound
from apps.game.services.payment_manager import ResetManager
from apps.game.betting.betting_manager import BettingManager
from apps.game.services.connect_manager import ConnectManager
from apps.game.services.dispatch_action_manager import DispatchActionManager
from apps.game.betting.rollback_manager import RollbackManger
from apps.game.services.connect_manager import DealerConnectManager
from apps.game.tasks import wait_player
from apps.game.services.utils import get_time_left_in_seconds, catch_error

logger = logging.getLogger("player_actions")
formatter = logging.Formatter("%(asctime)s - %(message)s")

fh = logging.FileHandler("player_actions.log")
fh.setLevel(level=logging.INFO)
fh.setFormatter(formatter)

logger.addHandler(fh)

mgr = socketio.AsyncRedisManager(settings.WS_MESSAGE_QUEUE)
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=[],
    client_manager=mgr,
    logger=True,
    engineio_logger=True,
)

external_sio = socketio.AsyncRedisManager(settings.WS_MESSAGE_QUEUE, write_only=True)
sio_app = socketio.ASGIApp(sio)

from apps.game.cards.cards_manager import EuropeanCardsManager, AmericanCardsManager
from apps.game.cards.actions_card_manager import ActionCardManager


@sio.event
@catch_error
async def connect(sid, environ):
    game_id = parse_qs(environ["QUERY_STRING"]).get("game_id")[0]
    token = parse_qs(environ["QUERY_STRING"]).get("token")
    jwt_token = parse_qs(environ["QUERY_STRING"]).get("jwt_token")
    # stream_token = await generate_token_for_stream(game_id)
    if jwt_token and game_id:
        dealer_connect_manager = DealerConnectManager(game_id, sid, jwt_token[0])
        send_data, _ = await dealer_connect_manager.connect_to_game()
        sio.enter_room(sid, game_id)
        await sio.emit("on_connect_data", send_data, to=sid)
    elif game_id and token:
        connect_manager = ConnectManager(game_id, token[0], sid)
        send_data, merchant_id = await connect_manager.connect_to_game()
        sio.enter_room(sid, game_id)
        sio.enter_room(sid, sid)
        sio.enter_room(sid, f"{send_data['user_id']}:{merchant_id}")
        await sio.emit("on_connect_data", send_data, to=sid)
        await external_sio.emit(
            "send_chat_message",
            data={
                "message": f"New Player - {send_data['user_name']}",
                "player": "BJ",
                "player_count": await redis_cache.get(f"{game_id}:player_count"),
            },
            room=game_id,
        )
    else:
        await sio.emit(
            "error", {"message": "please specify correct query parameters"}, to=sid
        )
        await sio.disconnect(sid)


@sio.event
@catch_error
async def place_bet(sid, data):
    user_session_data = await redis_cache.redis_cache.hgetall(sid)
    amount, bet_type, seat_number = (
        data["amount"],
        data["bet_type"],
        data["seat_number"],
    )
    betting_manager = BettingManager(user_session_data, sid, bet_type)
    response_data = await betting_manager.charge_user(amount, seat_number, bet_type)
    await sio.emit("bet_status", response_data, to=sid)
    await external_sio.emit(
        "new_bet",
        {
            "bet_type": bet_type,
            "seat_number": data["seat_number"],
            "total_bet": response_data["total_bet"],
            "bet": response_data[bet_type],
            "bet_list": response_data[f"{bet_type}_list"],
            "user_name": user_session_data["user_name"],
        },
        room=user_session_data["game_id"],
        skip_sid=sid,
    )


@sio.event
@catch_error
async def tip_dealer(sid, data):
    user_session_data = await redis_cache.redis_cache.hgetall(sid)
    amount = data["amount"]
    betting_manager = BettingManager(user_session_data, sid, "tip")
    response_data = await betting_manager.tip_dealer(amount, user_session_data)
    await sio.emit("tip_status", response_data, to=sid)
    await external_sio.emit(
        "send_chat_message",
        {
            "player": "MIMA",
            "message": f"{user_session_data['user_name']} tipped dealer ${amount}",
        },
        room=user_session_data["game_id"],
    )


@sio.event
@catch_error
async def make_repeat(sid, _):
    session_data = await redis_cache.redis_cache.hgetall(sid)
    betting_manager = BettingManager(session_data, sid, "repeat")
    response_data = await betting_manager.make_repeat(session_data)
    await sio.emit("repeat_status", response_data, to=sid)


@sio.event
@catch_error
async def make_rollback(sid, data):
    user_session_data = await redis_cache.redis_cache.hgetall(sid)
    rollback_type, seat_number = data["rollback_type"], data["seat_number"]
    rollback_manager = RollbackManger(user_session_data, sid, rollback_type)
    response_data = await rollback_manager.make_rollback(seat_number, rollback_type)
    # TODO remove balance key from response data

    await sio.emit("rollback_status", response_data, to=sid)
    await external_sio.emit(
        "new_rollback",
        response_data,
        room=user_session_data["game_id"],
        skip_sid=sid,
    )


@sio.event
@catch_error
async def make_action(sid, data):
    action_type = data["action_type"]
    user_session_data = await redis_cache.redis_cache.hgetall(sid)
    action_manager = DispatchActionManager(
        session_data=user_session_data,
        round_id=data["round_id"],
        sid=sid,
        action_type=action_type,
    )
    if action_type in ["double", "split"]:
        await action_manager.make_action()
    else:
        event_name, response, game_id = await action_manager.make_action()
        await external_sio.emit(event_name, response, room=game_id)


@sio.event
@catch_error
async def make_insurance(sid, data):
    action_type = data["action_type"]
    seat_number = data.get("seat_number", 0)
    value = data.get("value")
    user_session_data = await redis_cache.redis_cache.hgetall(sid)
    action_manager = DispatchActionManager(
        user_session_data,
        round_id=data["round_id"],
        sid=sid,
        action_type=action_type,
        seat_number=seat_number,
    )
    await action_manager.make_insurance(value)


@sio.event
@catch_error
async def make_auto_stand(sid, data):
    action_type = "auto_stand"
    user_session_data = await redis_cache.redis_cache.hgetall(sid)
    action_manager = DispatchActionManager(
        session_data=user_session_data,
        round_id=data["round_id"],
        sid=sid,
        action_type=action_type,
    )
    event_name, response, game_id = await action_manager.make_action()
    await external_sio.emit(event_name, response, room=game_id)


@sio.event
@catch_error
async def scan_card(sid, data):
    user_session_data = await redis_cache.redis_cache.hgetall(sid)
    round_id, card = data["round_id"], data["card"]
    game_type = await redis_cache.get_or_cache_game_type(user_session_data["game_id"])
    if game_type == "european":
        card_manager = EuropeanCardsManager(user_session_data, round_id)
    else:
        card_manager = AmericanCardsManager(user_session_data, round_id)
    await card_manager.handle_card_dealing(card)


@sio.event
@catch_error
async def action_cards(sid, data):
    round_id, card = data["round_id"], data["card"]
    user_session_data = await redis_cache.redis_cache.hgetall(sid)
    action_card_manager = ActionCardManager(user_session_data, round_id)
    event_name, data, room_name = await action_card_manager.scan_card(card)
    await external_sio.emit(event_name, data, room=room_name)


@sio.event
@catch_error
async def dealer_cards(sid, data):
    round_id, card = data["round_id"], data["card"]
    user_session_data = await redis_cache.redis_cache.hgetall(sid)
    action_card_manager = ActionCardManager(user_session_data, round_id)
    await action_card_manager.scan_dealer_card(card)


@sio.event
@catch_error
async def change_dealer(sid, data):
    game_id, dealer_name = data["game_id"], data["dealer_name"]
    await redis_cache.set(f"{game_id}:dealer_name", dealer_name)
    await GameRound.get_motor_collection().find_one_and_update(
        {"game_id": game_id, "finished": False}, {"$set": {"dealer_name": dealer_name}}
    )
    await external_sio.emit("change_dealer", {"dealer_name": dealer_name}, room=game_id)


@sio.event
@catch_error
async def reset_game(sid, data):
    round_id, game_id = data["round_id"], data["game_id"]
    game_round = await GameRound.get(PydanticObjectId(round_id))
    reset_manager = ResetManager(game_id, game_round)
    await reset_manager.reset()


@sio.event
@catch_error
async def send_chat_message(sid, data):
    user_session_data = await redis_cache.redis_cache.hgetall(sid)
    await external_sio.emit(
        "send_chat_message",
        data={
            "message": data.get("message"),
            "player": user_session_data["user_name"],
        },
        room=user_session_data["game_id"],
    )


@sio.event
async def disconnect(sid):
    try:

        user_session_data = await redis_cache.redis_cache.hgetall(sid)
        await redis_cache.redis_cache.decr(
            f"{user_session_data['game_id']}:player_count"
        )
        await external_sio.emit(
            "player_count",
            await redis_cache.get(f"{user_session_data['game_id']}:player_count"),
            room=user_session_data["game_id"],
        )
        game_players = await GamePlayer.find(
            {
                "user_id": user_session_data["user_id"],
                "merchant": user_session_data["merchant_id"],
                "game_id": user_session_data["game_id"],
                "archived": False,
            }
        ).to_list(14)
        for game_player in game_players:
            if game_player.player_turn and game_player.making_decision:
                if int(game_player.decision_time) > int(
                    game_player.inactivity_check_time
                ):
                    wait_player.apply_async(
                        args=[
                            str(game_player.id),
                            game_player.game_id,
                            len(game_player.action_list),
                        ],
                        countdown=get_time_left_in_seconds(game_player.decision_time)
                        + 1,
                    )
                    await GamePlayer.get_motor_collection().find_one_and_update(
                        {"_id": PydanticObjectId(game_player.id)},
                        {"$set": {"inactivity_check_time": game_player.decision_time}},
                    )
                await GamePlayer.get_motor_collection().update_many(
                    {
                        "user_id": user_session_data["user_id"],
                        "merchant": user_session_data["merchant_id"],
                        "game_id": user_session_data["game_id"],
                        "archived": False,
                    },
                    {"$set": {"is_active": False}},
                )
            else:
                await GamePlayer.get_motor_collection().update_many(
                    {
                        "user_id": user_session_data["user_id"],
                        "merchant": user_session_data["merchant_id"],
                        "game_id": user_session_data["game_id"],
                        "archived": False,
                    },
                    {"$set": {"is_active": False}},
                )
        sio.leave_room(sid, sid)
        sio.leave_room(sid, user_session_data["game_id"])
        sio.leave_room(
            sid, f'{user_session_data["user_id"]}:{user_session_data["merchant_id"]}'
        )

        await sio.disconnect(sid)
        await redis_cache.redis_cache.delete(sid)

        print(sid, "disconnected")
    except KeyError as e:
        print(str(e))
        # user_session_data = await redis_cache.redis_cache.hgetall(sid)
        # await redis_cache.redis_cache.decr(f"{user_session_data['game_id']}:player_count")
        # await external_sio.emit(
        #     "player_count",
        #     await redis_cache.get(f"{user_session_data['game_id']}:player_count"),
        #     room=user_session_data['game_id']
        # )
        await sio.disconnect(sid)
        print(sid, "disconnected")
