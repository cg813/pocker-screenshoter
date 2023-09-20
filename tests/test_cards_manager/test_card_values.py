import pytest

from apps.connections import redis_cache
from apps.game.cards.cards_manager import EuropeanCardsManager
from apps.game.services.connect_manager import ConnectManager
from tests.helpers import (
    TEST_GAME_ID,
    TEST_ROUND_ID,
    base_listener,
    connect_socket,
    get_round_and_finish_betting_time,
    mock_check_if_user_can_connect,
)


@pytest.mark.asyncio
async def test_get_card_values_with_one_player(monkeypatch, betting_manager):
    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )
    connect_data, client = await connect_socket(TEST_GAME_ID, "test_token")

    await betting_manager.charge_user(10, 1)
    user_session_data = await redis_cache.redis_cache.hgetall("test_sid")
    card_manager = EuropeanCardsManager(user_session_data, TEST_ROUND_ID)
    await get_round_and_finish_betting_time()
    await card_manager.handle_card_dealing("14S")
    await card_manager.handle_card_dealing("15C")

    data = await base_listener(
        card_manager.handle_card_dealing, "send_hand_value", client, "18S"
    )
    assert data == {"seat_number": 1, "score": "12", "card": "18S"}
    await client.disconnect()


@pytest.mark.asyncio
async def test_get_card_values_with_two_player(monkeypatch, betting_manager):
    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )
    connect_data, client = await connect_socket(TEST_GAME_ID, "test_token")

    await betting_manager.charge_user(10, 1)
    await betting_manager.charge_user(20, 3)
    user_session_data = await redis_cache.redis_cache.hgetall("test_sid")
    card_manager = EuropeanCardsManager(user_session_data, TEST_ROUND_ID)
    await get_round_and_finish_betting_time()
    await card_manager.handle_card_dealing("14S")
    await card_manager.handle_card_dealing("15C")
    await card_manager.handle_card_dealing("19C")

    data = await base_listener(
        card_manager.handle_card_dealing, "send_hand_value", client, "18S"
    )
    second_player = await base_listener(
        card_manager.handle_card_dealing, "send_hand_value", client, "1KD"
    )
    assert data == {"seat_number": 1, "score": "12", "card": "18S"}
    assert second_player == {"seat_number": 3, "score": "15", "card": "1KD"}
    await client.disconnect()
