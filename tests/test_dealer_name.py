import pytest

from apps.connections import redis_cache
from apps.game.services.connect_manager import ConnectManager
from apps.game.documents import GameRound
from .helpers import (
    mock_check_if_user_can_connect,
    connect_socket,
    base_helper,
    TEST_GAME_ID,
)


@pytest.mark.asyncio
async def test_receiving_dealer_name_on_connect(monkeypatch):
    await redis_cache.redis_cache.set(f"{TEST_GAME_ID}:dealer_name", "Natasha")
    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )
    connect_manager = ConnectManager(TEST_GAME_ID, "test_token", "test_sid")
    data, _ = await connect_manager.connect_to_game()
    await redis_cache.redis_cache.hgetall(connect_manager.sid)
    assert data.get("dealer_name") == "Natasha"


@pytest.mark.asyncio
async def test_setting_dealer_name_to_current_round(monkeypatch):
    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )
    _, client = await connect_socket(TEST_GAME_ID, "test_sid")
    await base_helper(
        client,
        "change_dealer",
        "change_dealer",
        {"game_id": TEST_GAME_ID, "dealer_name": "Natasha"},
    )
    game_round = await GameRound.find_one({})
    assert game_round.dealer_name == "Natasha"

    await client.disconnect()
