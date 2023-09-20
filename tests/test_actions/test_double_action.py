import pytest
import httpx

from apps.connections import redis_cache
from apps.game.documents import GamePlayer
from apps.game.cards.cards_manager import EuropeanCardsManager
from apps.game.services.custom_exception import ValidationError
from apps.game.services.dispatch_action_manager import DispatchActionManager
from tests.helpers import (
    TEST_ROUND_ID,
    base_helper,
    base_listener,
    get_players,
    get_round_and_finish_betting_time,
    scan_multiple_cards,
    TEST_SESSION_DATA,
    mock_httpx_request,
)


@pytest.mark.asyncio
async def test_double_action(betting_manager, monkeypatch):
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_httpx_request)
    await betting_manager.charge_user(10, 1)
    card_manager = EuropeanCardsManager(TEST_SESSION_DATA, TEST_ROUND_ID)
    await get_round_and_finish_betting_time()
    await scan_multiple_cards(["14S", "15H", "19C"], card_manager)
    dispatch_manager = DispatchActionManager(
        TEST_SESSION_DATA, TEST_ROUND_ID, "test_sid", "double"
    )
    await dispatch_manager.make_action()

    game_player = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    assert game_player.last_action == "double"
    assert game_player.bet == 20
    assert game_player.bet_list == [10, 10]
    assert game_player.action_list[0].get("bet") == 10
    assert game_player.action_list[1].get("double") == 10
    assert game_player.total_bet == 20
    assert game_player.making_decision is False
    assert game_player.player_turn is True


@pytest.mark.asyncio
async def test_double_action_with_insufficient_funds(socket_client):
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
    decision_data = await base_listener(
        scan_multiple_cards,
        "make_decision",
        socket_client,
        ["19S", "14C", "14D"],
        card_manager,
    )
    assert decision_data == {
        "score": 13,
        "actions": ["stand", "hit"],
        "cards": ["19S", "14D"],
    }
    await socket_client.disconnect()


@pytest.mark.asyncio
async def test_double_action_when_time_is_over(betting_manager):
    await betting_manager.charge_user(10, 1)
    card_manager = EuropeanCardsManager(TEST_SESSION_DATA, TEST_ROUND_ID)
    await get_round_and_finish_betting_time()
    await scan_multiple_cards(["14S", "15H", "19C"], card_manager)
    game_player: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    game_player.decision_time = float(game_player.decision_time) - 20
    await game_player.save()
    dispatch_manager = DispatchActionManager(
        TEST_SESSION_DATA, TEST_ROUND_ID, "test_sid", "double"
    )
    with pytest.raises(ValidationError) as error:
        await dispatch_manager.make_action()
        assert str(error) == "Time for making decision is over"


@pytest.mark.asyncio
async def test_double_action_with_incorrect_cards(base_client):
    (socket_client,) = await get_players(1)
    await base_helper(
        socket_client,
        "bet_status",
        "place_bet",
        {"amount": 10, "bet_type": "bet", "seat_number": 1},
    )
    await scan_multiple_cards(["1TS", "1AC", "1AD"])
    data = await base_helper(
        socket_client,
        "error",
        "make_action",
        {"round_id": TEST_ROUND_ID, "action_type": "double"},
    )
    assert data == {"message": "Can not find game player or it is not your turn"}
    await socket_client.disconnect()


@pytest.mark.asyncio
async def test_double_with_three_cards(base_client):
    (socket_client,) = await get_players(1)
    await base_helper(
        socket_client,
        "bet_status",
        "place_bet",
        {"amount": 10, "bet_type": "bet", "seat_number": 1},
    )
    card_manager = EuropeanCardsManager(TEST_SESSION_DATA, TEST_ROUND_ID)
    await base_listener(
        scan_multiple_cards,
        "make_decision",
        socket_client,
        ["13C", "18S", "13H"],
        card_manager,
    )
    await base_helper(
        socket_client,
        "player_action",
        "make_action",
        {"round_id": TEST_ROUND_ID, "action_type": "hit"},
    )
    await base_helper(
        socket_client,
        "make_decision",
        "action_cards",
        {"round_id": TEST_ROUND_ID, "card": "13C"},
    )
    print_data = await base_helper(
        socket_client,
        "error",
        "make_action",
        {"round_id": TEST_ROUND_ID, "action_type": "double"},
    )
    assert print_data == {"message": "Action double is not allowed"}
    await socket_client.disconnect()


@pytest.mark.asyncio
async def test_possible_action_with_not_enought_deposit(socket_client):
    await base_helper(
        socket_client,
        "bet_status",
        "place_bet",
        {"amount": 10, "bet_type": "bet", "seat_number": 1},
    )
    game_player: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    game_player.deposit = 2
    await game_player.save()
    await redis_cache.set_user_balance_in_cache(
        game_player.user_id, game_player.merchant, 4
    )
    card_manager = EuropeanCardsManager(TEST_SESSION_DATA, TEST_ROUND_ID)
    decision_data = await base_listener(
        scan_multiple_cards,
        "make_decision",
        socket_client,
        ["19S", "14C", "14D"],
        card_manager,
    )
    assert decision_data == {
        "score": 13,
        "actions": ["stand", "hit"],
        "cards": ["19S", "14D"],
    }
    await socket_client.disconnect()
