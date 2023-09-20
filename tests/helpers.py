import asyncio
import os
from typing import Callable, List

import socketio
from beanie import PydanticObjectId
from bson import ObjectId

from apps.connections import redis_cache
from apps.game.documents import Game, GameRound, Merchant, GamePlayer
from apps.game.models import GameMerchantModel
from apps.game.cards.cards_manager import EuropeanCardsManager
from apps.game.services.utils import get_timestamp


CASINO_POKER_BASE_URL = os.environ.get("CASINO_POKER_BASE_URL")
TEST_GAME_ID = "507f1f77bcf86cd799439011"
TEST_ROUND_ID = "5349b4ddd2781d08c09890f3"
TEST_MERCHANT_ID = "507f1f77bcf86cd799439011"
TEST_DEPOSIT = 100092

TEST_SESSION_DATA = {
    "user_name": "test_user",
    "game_id": TEST_GAME_ID,
    "user_token": "test_token",
    "merchant_id": TEST_MERCHANT_ID,
    "user_id": "2",
}


async def connect_socket(game_id: str, user_token: str, jwt_token: str = ""):

    game_data_future = asyncio.get_running_loop().create_future()

    sio = socketio.AsyncClient()

    @sio.event
    def on_connect_data(data):
        game_data_future.set_result(data)

    if jwt_token:

        await sio.connect(
            f"http://localhost:4000/?game_id={game_id}&jwt_token={jwt_token}",
            socketio_path="/ws/blackjack/socket.io",
            transports=["websocket"],
        )
    else:
        await sio.connect(
            f"http://localhost:4000/?game_id={game_id}&token={user_token}",
            socketio_path="/ws/blackjack/socket.io",
            transports=["websocket"],
        )

    return await asyncio.wait_for(game_data_future, timeout=7.0), sio


async def connect_socket_with_invalid_data(
    game_id: str, user_token: str, sio: socketio.AsyncClient
):

    game_data_error_future = asyncio.get_running_loop().create_future()

    @sio.event
    def error(data):
        game_data_error_future.set_result(data)

    await sio.connect(
        f"http://localhost:4000/?game_id={game_id}&token={user_token}",
        socketio_path="/ws/blackjack/socket.io",
        transports=["websocket"],
    )

    return await asyncio.wait_for(game_data_error_future, timeout=2.0)


async def connect_socket_with_nonexistent_game(
    game_id: str, user_token: str, sio: socketio.AsyncClient
):

    game_data_error_future = asyncio.get_running_loop().create_future()

    @sio.event
    def error(data):
        game_data_error_future.set_result(data)

    await sio.connect(
        f"http://localhost:4000/?game_id=622ef5de68b111bad1e6b2ad&token={user_token}",
        socketio_path="/ws/blackjack/socket.io",
        transports=["websocket"],
    )

    return await asyncio.wait_for(game_data_error_future, timeout=2.0)


async def base_helper(
    sio: socketio.AsyncClient,
    receiver_event_name: str,
    send_event_name: str,
    send_data: dict,
):
    base_future = asyncio.get_running_loop().create_future()

    @sio.on(receiver_event_name)
    def receiver_event(data):
        base_future.set_result(data)

    await sio.emit(send_event_name, send_data)

    return await asyncio.wait_for(base_future, timeout=3)


async def create_game_and_merchant_for_testing():
    game = Game(
        id=PydanticObjectId(TEST_GAME_ID),
        name="test_game",
        type="european",
        game_status=True,
        table_stream_key_1="123",
        table_stream_key_2="456",
    )
    await game.save()
    game_merchant_model = GameMerchantModel(
        game_id=str(game.id),
        game_name="test_game",
        min_bet=10,
        max_bet=200,
        bet_range=[5, 10, 20, 50],
        is_active=True,
    )
    merchant = Merchant(
        id=PydanticObjectId(TEST_MERCHANT_ID),
        name="test_merchant",
        api_key="test_api_key",
        games=[game_merchant_model],
        transaction_url="http://backend:8000/api/games/transaction/",
        bet_url="http://backend:8000/api/games/transaction/",
        win_url="http://backend:8000/api/games/transaction/",
        rollback_url="http://backend:8000/api/games/transaction/",
        validate_token_url="http://backend:8000/api/games/check/",
        get_balance_url="http://backend:8000/api/games/get_balance/",
        schema_type="snake",
    )
    await merchant.save()


async def create_game_round_for_testing():
    await GameRound.get_motor_collection().insert_one(
        {
            "_id": ObjectId(TEST_ROUND_ID),
            "created_at": get_timestamp(),
            "updated_at": get_timestamp(),
            "card_count": 0,
            "game_id": TEST_GAME_ID,
            "round_id": "Test_round",
            "start_timestamp": get_timestamp(15),
            "insurance_timestamp": 0,
            "dealer_cards": [],
            "show_dealer_cards": False,
            "was_reset": False,
            "finished": False,
            "dealer_name": "",
            "finished_dealing": False,
            "prev_round_id": None,
        }
    )


async def mock_check_if_user_can_connect(self):
    self.merchant_id = TEST_MERCHANT_ID
    self.merchant_data = await redis_cache.get_or_cache_merchant(
        TEST_MERCHANT_ID, TEST_GAME_ID
    )
    return {
        "total_balance": TEST_DEPOSIT,
        "currency": "USD",
        "user_name": "test_user",
        "user_id": 2,
        "game_id": TEST_GAME_ID,
    }


async def mock_check_if_user_can_connect_witch_nonexistent_game(self):
    self.merchant_id = TEST_MERCHANT_ID
    self.merchant_data = await redis_cache.get_or_cache_merchant(
        TEST_MERCHANT_ID, "618e39136a419d06ecf65eb4"
    )
    return {
        "deposit": TEST_DEPOSIT,
        "currency": "USD",
        "username": "test_user",
        "user_id": 2,
    }


async def scan_multiple_cards(cards: List, cards_manager=None):
    if cards_manager:
        for card in cards:
            await cards_manager.handle_card_dealing(card)
    else:
        cards_manager = EuropeanCardsManager(TEST_SESSION_DATA, TEST_ROUND_ID)
        for card in cards:
            await cards_manager.handle_card_dealing(card)


async def get_round_and_finish_betting_time():
    game_round: GameRound = await GameRound.find_one({})
    game_round.start_timestamp = get_timestamp() - 20
    await game_round.save()


async def get_round_and_finish_insurance_time():
    game_round: GameRound = await GameRound.find_one({})
    game_round.insurance_timestamp = get_timestamp() - 20
    await game_round.save()


async def base_listener(
    func: Callable, event_name: str, client: socketio.AsyncClient, *arg
):
    base_listener_feature = asyncio.get_running_loop().create_future()

    @client.on(event_name)
    def get_data(data):
        base_listener_feature.set_result(data)

    await func(*arg)

    return await asyncio.wait_for(base_listener_feature, timeout=2.0)


async def get_players(number_of_players) -> List[socketio.AsyncClient]:
    players = []
    for i in range(number_of_players):
        _, client = await connect_socket(TEST_GAME_ID, f"test_sid_{i}")
        players.append(client)
    return players


class MockResponse:
    def __init__(self, status_code: int, status: str):
        self.status_code = status_code
        self.status = status

    def json(self) -> dict:
        return {"status": self.status, "total_balance": 980}


def mock_request(*_, **kwargs):
    return MockResponse(200, "Ok")


def mock_bad_request(*_, **kwargs):
    return MockResponse(200, "Failed")


async def mock_httpx_request(*_, **kwargs):
    return MockResponse(200, "Ok")


async def mock_httpx_bad_request(*_, **kwargs):
    return MockResponse(200, "Failed")


def mock_send_to_merchant(*_, **kwargs):
    pass


def mock_clean_seats(self):
    pass


async def mock_make_insurance(self, value: bool) -> None:
    self.game_player = await GamePlayer.find_one(
        {
            "game_round": self.round_id,
            "seat_number": self.seat_number,
            "sid": self.sid,
        }
    )
    self.validate_action()
    await self.validate_action_for_insurance()

    if value is True:
        amount = self.game_player.bet / 2
        updated_game_player = (
            await GamePlayer.get_motor_collection().find_one_and_update(
                {"_id": ObjectId(self.game_player.id)},
                {
                    "$set": {
                        "total_bet": self.game_player.total_bet + amount,
                        "deposit": self.game_player.deposit - amount,
                        "bet_list": self.game_player.bet_list + [amount],
                        "action_list": self.game_player.action_list
                        + [{"insurance": amount}],
                        "last_action": "insurance",
                        "insured": True,
                    }
                },
                return_document=True,
            )
        )

        await redis_cache.set_user_balance_in_cache(
            updated_game_player["user_id"],
            updated_game_player["merchant"],
            float(updated_game_player["deposit"]),
        )
    else:
        self.game_player.insured = False
        self.game_player.last_action = "insurance"
        await self.game_player.save()


async def mock_make_double(self) -> None:
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

    amount = self.game_player.bet
    updated_game_player = await GamePlayer.get_motor_collection().find_one_and_update(
        {"_id": ObjectId(self.game_player.id)},
        {
            "$set": {
                "total_bet": self.game_player.total_bet + amount,
                "deposit": self.game_player.deposit - amount,
                "bet": self.game_player.bet + amount,
                "bet_list": self.game_player.bet_list + [amount],
                "action_list": self.game_player.action_list + [{"double": amount}],
                "last_action": "double",
                "making_decision": False,
            }
        },
        return_document=True,
    )

    await redis_cache.set_user_balance_in_cache(
        updated_game_player["user_id"],
        updated_game_player["merchant"],
        float(updated_game_player["deposit"]),
    )
