import pytest

from apps.game.documents import GamePlayer, GameRound
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
)


@pytest.mark.asyncio
async def test_hit_action(base_client):
    (socket_client,) = await get_players(1)
    await base_helper(
        socket_client,
        "bet_status",
        "place_bet",
        {"amount": 10, "bet_type": "bet", "seat_number": 1},
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
        "actions": ["stand", "hit", "double"],
        "cards": ["19S", "14D"],
    }

    data = await base_helper(
        socket_client,
        "player_action",
        "make_action",
        {"round_id": TEST_ROUND_ID, "action_type": "hit"},
    )
    assert data == {"seat_number": 1, "action_type": "hit"}
    game_player = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    assert game_player.last_action == "hit"
    assert game_player.making_decision is False
    assert game_player.player_turn is True
    await socket_client.disconnect()


@pytest.mark.asyncio
async def test_hit_action_2(base_client):
    (socket_client,) = await get_players(1)
    await base_helper(
        socket_client,
        "bet_status",
        "place_bet",
        {"amount": 10, "bet_type": "bet", "seat_number": 1},
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
        "actions": ["stand", "hit", "double"],
        "cards": ["19S", "14D"],
    }

    data = await base_helper(
        socket_client,
        "player_action",
        "make_action",
        {"round_id": TEST_ROUND_ID, "action_type": "hit"},
    )
    assert data == {"seat_number": 1, "action_type": "hit"}
    game_player = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    assert game_player.last_action == "hit"
    assert game_player.making_decision is False
    assert game_player.player_turn is True
    data = await base_helper(
        socket_client,
        "make_decision",
        "action_cards",
        {"round_id": TEST_ROUND_ID, "card": "15C"},
    )
    assert data == {
        "score": 18,
        "actions": ["stand", "hit"],
        "cards": ["19S", "14D", "15C"],
    }
    game_player = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    assert game_player.cards == ["19S", "14D", "15C"]
    assert game_player.making_decision is True
    assert game_player.player_turn is True
    await socket_client.disconnect()


@pytest.mark.asyncio
async def test_hit_action_when_time_is_over(betting_manager):
    await betting_manager.charge_user(10, 1)
    card_manager = EuropeanCardsManager(TEST_SESSION_DATA, TEST_ROUND_ID)
    await get_round_and_finish_betting_time()
    await scan_multiple_cards(["14S", "15H", "19C"], card_manager)
    game_player: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    game_player.decision_time = float(game_player.decision_time) - 20
    await game_player.save()
    dispatch_manager = DispatchActionManager(
        TEST_SESSION_DATA, TEST_ROUND_ID, "test_sid", "hit"
    )
    with pytest.raises(ValidationError) as error:
        await dispatch_manager.make_action()
        assert str(error) == "Time for making decision is over"


@pytest.mark.asyncio
async def test_move_to_next_player(base_client):
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
        {"amount": 10, "bet_type": "bet", "seat_number": 3},
    )
    card_manager = EuropeanCardsManager(TEST_SESSION_DATA, TEST_ROUND_ID)
    await base_listener(
        scan_multiple_cards,
        "make_decision",
        socket_client,
        ["19S", "14C", "18D", "17S", "16D"],
        card_manager,
    )
    data = await base_helper(
        socket_client,
        "player_action",
        "make_action",
        {"round_id": TEST_ROUND_ID, "action_type": "hit"},
    )
    assert data == {"seat_number": 1, "action_type": "hit"}
    game_player = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    assert game_player.last_action == "hit"
    assert game_player.making_decision is False
    assert game_player.player_turn is True
    await base_helper(
        socket_client_2,
        "make_decision",
        "action_cards",
        {"round_id": TEST_ROUND_ID, "card": "15C"},
    )
    seat_1_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.seat_number == 1
    )
    seat_2_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.seat_number == 3
    )
    assert seat_1_game_player.player_turn is False
    assert seat_1_game_player.making_decision is False
    assert seat_2_game_player.player_turn is True
    assert seat_2_game_player.making_decision is True
    await socket_client.disconnect()
    await socket_client_2.disconnect()


@pytest.mark.asyncio
async def test_finish_dealing(base_client):
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
        {"amount": 10, "bet_type": "bet", "seat_number": 3},
    )
    card_manager = EuropeanCardsManager(TEST_SESSION_DATA, TEST_ROUND_ID)
    await base_listener(
        scan_multiple_cards,
        "make_decision",
        socket_client,
        ["19S", "18C", "18D", "17S", "16D"],
        card_manager,
    )
    data = await base_helper(
        socket_client,
        "player_action",
        "make_action",
        {"round_id": TEST_ROUND_ID, "action_type": "hit"},
    )
    assert data == {"seat_number": 1, "action_type": "hit"}
    game_player = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    assert game_player.last_action == "hit"
    assert game_player.making_decision is False
    assert game_player.player_turn is True
    await base_helper(
        socket_client_2,
        "make_decision",
        "action_cards",
        {"round_id": TEST_ROUND_ID, "card": "15C"},
    )
    seat_1_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.seat_number == 1
    )
    seat_2_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.seat_number == 3
    )
    assert seat_1_game_player.player_turn is False
    assert seat_1_game_player.making_decision is False
    assert seat_2_game_player.player_turn is True
    assert seat_2_game_player.making_decision is True
    await base_helper(
        socket_client_2,
        "player_action",
        "make_action",
        {"round_id": TEST_ROUND_ID, "action_type": "hit"},
    )
    await base_helper(
        socket_client_2,
        "scan_dealer_card",
        "action_cards",
        {"round_id": TEST_ROUND_ID, "card": "19C"},
    )

    seat_2_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.seat_number == 3
    )
    assert seat_2_game_player.player_turn is False
    assert seat_2_game_player.making_decision is False
    game_round = await GameRound.find_one({})
    assert game_round.finished_dealing is True
    await socket_client.disconnect()
    await socket_client_2.disconnect()


@pytest.mark.asyncio
async def test_hit_action_with_incorrect_sid(base_client):
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
    await base_listener(
        scan_multiple_cards,
        "make_decision",
        socket_client,
        ["19S", "14C", "14D", "13S", "18H"],
        card_manager,
    )

    data = await base_helper(
        socket_client_2,
        "error",
        "make_action",
        {"round_id": TEST_ROUND_ID, "action_type": "hit"},
    )
    assert data == {"message": "Player is not allowed to make action"}
    await socket_client.disconnect()
    await socket_client_2.disconnect()


@pytest.mark.asyncio
async def test_message_on_hit(base_client):
    socket_client, socket_client_2 = await get_players(2)
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
        ["19S", "14C", "14D"],
        card_manager,
    )

    await base_helper(
        socket_client,
        "player_action",
        "make_action",
        {"round_id": TEST_ROUND_ID, "action_type": "hit"},
    )
    data = await base_helper(
        socket_client,
        "hand_value",
        "action_cards",
        {"round_id": TEST_ROUND_ID, "card": "19C"},
    )
    assert data == {"seat_number": 1, "score": "22", "card": "19C"}
    await socket_client.disconnect()
    await socket_client_2.disconnect()


@pytest.mark.asyncio
async def test_hit_with_incorrect_cards(base_client):
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
        {"round_id": TEST_ROUND_ID, "action_type": "hit"},
    )
    assert data == {"message": "Can not find game player or it is not your turn"}
    await socket_client.disconnect()
