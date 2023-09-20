import pytest
import httpx

from apps.connections import redis_cache
from apps.game.services.custom_exception import ValidationError
from apps.game.services.dispatch_action_manager import DispatchActionManager
from apps.game.cards.cards_manager import EuropeanCardsManager
from apps.game.documents import GamePlayer
from tests.helpers import (
    TEST_SESSION_DATA,
    TEST_ROUND_ID,
    base_helper,
    base_listener,
    get_round_and_finish_betting_time,
    scan_multiple_cards,
    get_round_and_finish_insurance_time,
    mock_httpx_request,
)


@pytest.mark.asyncio
async def test_making_insurance_with_value_true(betting_manager, monkeypatch):
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_httpx_request)
    await betting_manager.charge_user(10, 1)
    card_manager = EuropeanCardsManager(TEST_SESSION_DATA, TEST_ROUND_ID)
    await get_round_and_finish_betting_time()
    await scan_multiple_cards(["14S", "1AH", "19C"], card_manager)

    dispatch_manager = DispatchActionManager(
        TEST_SESSION_DATA, TEST_ROUND_ID, "test_sid", "insurance", 1
    )
    await dispatch_manager.make_insurance(True)

    game_player = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    assert game_player.last_action == "insurance"
    assert game_player.bet == 10
    assert game_player.bet_list == [10, 5]
    assert game_player.action_list[0].get("bet") == 10
    assert game_player.action_list[1].get("insurance") == 5
    assert game_player.total_bet == 15
    assert game_player.making_decision is False
    assert game_player.player_turn is False
    assert game_player.insured is True


@pytest.mark.asyncio
async def test_insurance_action_with_insufficient_funds(socket_client):
    await base_helper(
        socket_client,
        "bet_status",
        "place_bet",
        {"amount": 10, "bet_type": "bet", "seat_number": 1},
    )
    game_player: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    game_player.deposit = 4
    await game_player.save()
    await redis_cache.set_user_balance_in_cache(
        game_player.user_id, game_player.merchant, 4
    )
    card_manager = EuropeanCardsManager(TEST_SESSION_DATA, TEST_ROUND_ID)
    insurance_data = await base_listener(
        scan_multiple_cards,
        "make_insurance",
        socket_client,
        ["19S", "1AC", "14D"],
        card_manager,
    )
    assert insurance_data == {"decision_time": 6, "insurable_seats": [1]}
    data = await base_helper(
        socket_client,
        "error",
        "make_insurance",
        {"round_id": TEST_ROUND_ID, "action_type": "insurance", "seat_number": 1},
    )
    assert data == {"message": "Not enough fund to make insurance"}
    await socket_client.disconnect()


@pytest.mark.asyncio
async def test_insurance_action_when_insurance_time_is_over(betting_manager):
    await betting_manager.charge_user(10, 1)
    card_manager = EuropeanCardsManager(TEST_SESSION_DATA, TEST_ROUND_ID)
    await get_round_and_finish_betting_time()
    await scan_multiple_cards(["14S", "1AH", "19C"], card_manager)
    await get_round_and_finish_insurance_time()
    dispatch_manager = DispatchActionManager(
        TEST_SESSION_DATA, TEST_ROUND_ID, "test_sid", "insurance", 1
    )
    with pytest.raises(ValidationError) as error:
        await dispatch_manager.make_insurance(value=True)
        assert str(error) == "Time for making insurance is over"


@pytest.mark.asyncio
async def test_insurance_socket_message_when_insurance_time_is_over(socket_client):
    await base_helper(
        socket_client,
        "bet_status",
        "place_bet",
        {"amount": 10, "bet_type": "bet", "seat_number": 1},
    )
    card_manager = EuropeanCardsManager(TEST_SESSION_DATA, TEST_ROUND_ID)
    insurance_data = await base_listener(
        scan_multiple_cards,
        "make_insurance",
        socket_client,
        ["19S", "1AC", "14D"],
        card_manager,
    )
    assert insurance_data == {"decision_time": 6, "insurable_seats": [1]}
    await get_round_and_finish_insurance_time()
    data = await base_helper(
        socket_client,
        "error",
        "make_insurance",
        {"round_id": TEST_ROUND_ID, "action_type": "insurance", "seat_number": 1},
    )
    assert data == {"message": "Time for making insurance is over"}
    await socket_client.disconnect()


@pytest.mark.asyncio
async def test_making_insurance_when_dealer_does_not_have_ace(socket_client):
    await base_helper(
        socket_client,
        "bet_status",
        "place_bet",
        {"amount": 10, "bet_type": "bet", "seat_number": 1},
    )
    card_manager = EuropeanCardsManager(TEST_SESSION_DATA, TEST_ROUND_ID)
    await scan_multiple_cards(["19S", "1TC", "14D"], card_manager)
    data = await base_helper(
        socket_client,
        "error",
        "make_insurance",
        {"round_id": TEST_ROUND_ID, "action_type": "insurance", "seat_number": 1},
    )
    assert data == {
        "message": "You can not make insurance when dealer's first card is not an Ace"
    }
    await socket_client.disconnect()


@pytest.mark.asyncio
async def test_making_insurance_with_value_false(betting_manager, monkeypatch):
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_httpx_request)
    await betting_manager.charge_user(10, 1)
    card_manager = EuropeanCardsManager(TEST_SESSION_DATA, TEST_ROUND_ID)
    await get_round_and_finish_betting_time()
    await scan_multiple_cards(["14S", "1AH", "19C"], card_manager)

    dispatch_manager = DispatchActionManager(
        TEST_SESSION_DATA, TEST_ROUND_ID, "test_sid", "insurance", 1
    )
    await dispatch_manager.make_insurance(value=False)

    game_player = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    assert game_player.last_action == "insurance"
    assert game_player.bet == 10
    assert game_player.bet_list == [10]
    assert game_player.action_list[0].get("bet") == 10
    assert game_player.total_bet == 10
    assert game_player.making_decision is False
    assert game_player.player_turn is False
    assert game_player.insured is False


@pytest.mark.asyncio
async def test_making_insurance_when_player_has_bj(socket_client):
    await base_helper(
        socket_client,
        "bet_status",
        "place_bet",
        {"amount": 10, "bet_type": "bet", "seat_number": 1},
    )
    card_manager = EuropeanCardsManager(TEST_SESSION_DATA, TEST_ROUND_ID)
    await scan_multiple_cards(["1AS", "1AC", "1TD"], card_manager)
    data = await base_helper(
        socket_client,
        "error",
        "make_insurance",
        {"round_id": TEST_ROUND_ID, "action_type": "insurance", "seat_number": 1},
    )
    assert data == {"message": "Can not make Action"}
    await socket_client.disconnect()
