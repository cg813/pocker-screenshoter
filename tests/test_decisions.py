import pytest

from apps.game.documents import GameRound
from apps.game.cards.cards_manager import EuropeanCardsManager
from apps.game.services.connect_manager import ConnectManager

from .helpers import (
    TEST_GAME_ID,
    TEST_ROUND_ID,
    base_helper,
    base_listener,
    connect_socket,
    mock_check_if_user_can_connect,
    scan_multiple_cards,
    TEST_SESSION_DATA,
)


@pytest.mark.asyncio
async def test_getting_decision_event(monkeypatch):
    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )
    on_connect_data, client = await connect_socket(TEST_GAME_ID, "test_sid")
    await base_helper(
        client,
        "bet_status",
        "place_bet",
        {"amount": 10, "bet_type": "bet", "seat_number": 1},
    )
    card_manager = EuropeanCardsManager(TEST_SESSION_DATA, TEST_ROUND_ID)
    game_round = await GameRound.find_one({})
    game_round.start_timestamp = int(game_round.start_timestamp) - 20
    await game_round.save()
    decision_data = await base_listener(
        scan_multiple_cards,
        "make_decision",
        client,
        ["12C", "14C", "15S"],
        card_manager,
    )
    assert decision_data["actions"] == ["stand", "hit", "double"]
    assert decision_data["score"] == 7
    await client.disconnect()
