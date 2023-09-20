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
    get_players,
)


@pytest.mark.asyncio
async def test_getting_make_insurance(monkeypatch):
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
    insurance_data = await base_listener(
        scan_multiple_cards,
        "make_insurance",
        client,
        ["12C", "1AC", "15S"],
        card_manager,
    )
    assert insurance_data == {"decision_time": 6, "insurable_seats": [1]}
    await client.disconnect()


@pytest.mark.asyncio
async def test_getting_make_insurance_on_two_player(base_client):
    socket_client, socket_client_2 = await get_players(2)
    await base_helper(
        socket_client,
        "bet_status",
        "place_bet",
        {"amount": 10, "bet_type": "bet", "seat_number": 1},
    )
    await base_helper(
        socket_client_2,
        "bet_status",
        "place_bet",
        {"amount": 10, "bet_type": "bet", "seat_number": 5},
    )
    card_manager = EuropeanCardsManager(TEST_SESSION_DATA, TEST_ROUND_ID)
    insurance_data = await base_listener(
        scan_multiple_cards,
        "make_insurance",
        socket_client_2,
        ["12C", "12C", "1AS", "15D", "16D"],
        card_manager,
    )
    assert insurance_data == {"decision_time": 6, "insurable_seats": [1, 5]}
    await socket_client.disconnect()
    await socket_client_2.disconnect()


@pytest.mark.asyncio
async def test_scanning_card_before_insurance_time_is_over(monkeypatch):
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

    insurance_data = await base_listener(
        scan_multiple_cards,
        "make_insurance",
        client,
        ["12C", "1AC", "15S"],
        card_manager,
    )
    insurance_error = await base_helper(
        client, "error", "scan_card", {"round_id": TEST_ROUND_ID, "card": "16D"}
    )

    assert insurance_data == {"decision_time": 6, "insurable_seats": [1]}
    assert insurance_error == {"message": "Insurance decision time is not over"}
    await client.disconnect()


@pytest.mark.asyncio
async def test_getting_make_insurance_one_player_20_second_player_21(base_client):
    socket_client, socket_client_2 = await get_players(2)
    await base_helper(
        socket_client,
        "bet_status",
        "place_bet",
        {"amount": 10, "bet_type": "bet", "seat_number": 1},
    )
    await base_helper(
        socket_client_2,
        "bet_status",
        "place_bet",
        {"amount": 10, "bet_type": "bet", "seat_number": 5},
    )
    card_manager = EuropeanCardsManager(TEST_SESSION_DATA, TEST_ROUND_ID)
    insurance_data = await base_listener(
        scan_multiple_cards,
        "make_insurance",
        socket_client_2,
        ["12C", "1AC", "1AS", "15D", "1TD"],
        card_manager,
    )
    assert insurance_data == {"decision_time": 6, "insurable_seats": [1]}
    await socket_client.disconnect()
    await socket_client_2.disconnect()
