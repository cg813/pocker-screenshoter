import asyncio
import os
from asyncio.exceptions import CancelledError

import motor.motor_asyncio
import pytest
import socketio
from beanie import init_beanie
from httpx import AsyncClient

from apps.connections import redis_cache
from apps.game.documents import Game, GamePlayer, GameRound, Merchant
from apps.game.betting.betting_manager import BettingManager
from apps.game.services.connect_manager import ConnectManager
from apps.game.services.payment_manager import PaymentManager
from apps.game.betting.rollback_manager import RollbackManger
from main import app

from .helpers import (
    TEST_GAME_ID,
    TEST_SESSION_DATA,
    connect_socket,
    create_game_and_merchant_for_testing,
    create_game_round_for_testing,
    mock_check_if_user_can_connect,
    mock_httpx_request,
    mock_send_to_merchant,
    mock_clean_seats,
)
from .socketio_test_client import UvicornTestServer


@pytest.fixture(scope="session", autouse=True)
async def project_setup():
    client = motor.motor_asyncio.AsyncIOMotorClient(
        os.environ.get("BLACKJACK_MONGODB_URL")
    )
    await init_beanie(
        database=client["test_blackjack"],
        document_models=[Game, GamePlayer, GameRound, Merchant],
    )
    await redis_cache.init_cache()
    await Game.get_motor_collection().drop()
    await Merchant.get_motor_collection().drop()
    await create_game_and_merchant_for_testing()


@pytest.fixture(autouse=True)
async def tear_down():
    await GameRound.get_motor_collection().drop()
    await GamePlayer.get_motor_collection().drop()
    await redis_cache.redis_cache.flushdb()
    await create_game_round_for_testing()
    await redis_cache.redis_cache.hset("test_sid", mapping=TEST_SESSION_DATA)


@pytest.fixture()
async def betting_manager(monkeypatch):
    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )
    monkeypatch.setattr(AsyncClient, "post", mock_httpx_request)
    monkeypatch.setattr(PaymentManager, "send_to_merchant", mock_send_to_merchant)
    monkeypatch.setattr(BettingManager, "clean_seats", mock_clean_seats)
    connect_manager = ConnectManager(
        game_id=TEST_GAME_ID, user_token="test_token", sid="test_sid"
    )
    await connect_manager.connect_to_game()
    user_session_data = await redis_cache.redis_cache.hgetall("test_sid")
    betting_manager = BettingManager(user_session_data, "test_sid", "bet")
    yield betting_manager


@pytest.fixture()
async def betting_and_rollback_manager(monkeypatch):
    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )
    connect_manager = ConnectManager(
        game_id=TEST_GAME_ID, user_token="test_token", sid="test_sid"
    )
    await connect_manager.connect_to_game()
    user_session_data = await redis_cache.redis_cache.hgetall("test_sid")

    betting_manager = BettingManager(user_session_data, "test_sid", "bet")
    rollback_manager = RollbackManger(user_session_data, "test_sid", "bet")
    yield betting_manager, rollback_manager


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    try:
        pending = asyncio.all_tasks(loop)
        loop.run_until_complete(asyncio.gather(*pending))
    except CancelledError:
        loop.close()


@pytest.fixture(scope="session", autouse=True)
async def startup_and_shutdown_server():
    """Start server as test fixture and tear down after test"""
    server = UvicornTestServer()
    await server.up()
    yield
    await server.down()


@pytest.fixture()
async def client() -> AsyncClient:
    async with AsyncClient(app=app, base_url="http://localhost:4000") as client:
        yield client


@pytest.fixture()
async def base_client(monkeypatch):
    from apps.game.cards.cards_manager import EuropeanCardsManager

    def mock_check_scan_card(self):
        return None

    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )
    monkeypatch.setattr(
        EuropeanCardsManager, "check_can_scan_card", mock_check_scan_card
    )
    monkeypatch.setattr(PaymentManager, "send_to_merchant", mock_send_to_merchant)
    monkeypatch.setattr(BettingManager, "clean_seats", mock_clean_seats)


@pytest.fixture()
async def socket_client(base_client) -> socketio.AsyncClient:
    on_connect_data, client = await connect_socket(TEST_GAME_ID, "test_sid")
    yield client
