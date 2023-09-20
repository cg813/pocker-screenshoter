import pytest
from apps.game.documents import GamePlayer
from tests.helpers import (
    TEST_ROUND_ID,
    base_helper,
    get_players,
    scan_multiple_cards,
)


@pytest.mark.asyncio
async def test_skip_first_player_with_blackjack(base_client):
    """
    FIRST_PLAYER: init score: 21 -> should skip player
    SECOND_PLAYER: init score: 12 -> HIT -> score: 19 -> STAND
    FINALLY we should get scan dealer card event which means round is finished
    """
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
    await scan_multiple_cards(["1KC", "14C", "19S", "1AS", "18S"])
    await base_helper(
        socket_client_2,
        "player_action",
        "make_action",
        {"round_id": TEST_ROUND_ID, "action_type": "hit"},
    )
    await base_helper(
        socket_client_2,
        "make_decision",
        "action_cards",
        {"round_id": TEST_ROUND_ID, "card": "17D"},
    )
    first_game_player = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    assert first_game_player.player_turn is False
    assert first_game_player.making_decision is False
    assert first_game_player.last_action is None
    assert first_game_player.cards == ["1KC", "1AS"]

    second_game_player = await GamePlayer.find_one(GamePlayer.seat_number == 5)
    assert second_game_player.player_turn is True
    assert second_game_player.making_decision is True
    assert second_game_player.last_action == "hit"
    assert second_game_player.cards == ["14C", "18S", "17D"]
    await base_helper(
        socket_client_2,
        "scan_dealer_card",
        "make_action",
        {"round_id": TEST_ROUND_ID, "action_type": "stand"},
    )
    second_game_player = await GamePlayer.find_one(GamePlayer.seat_number == 5)
    assert second_game_player.player_turn is False
    assert second_game_player.making_decision is False
    assert second_game_player.last_action == "stand"
    assert second_game_player.cards == ["14C", "18S", "17D"]
    await socket_client.disconnect()
    await socket_client_2.disconnect()


@pytest.mark.asyncio
async def test_skip_to_third_player_when_first_2_players_have_bj(base_client):
    """
    FIRST_PLAYER: init score: 21
    SECOND_PLAYER: init score: 21
    THIRD_PLAYER: init score: 15
    FINALLY we should get scan dealer card event which means round is finished
    """
    socket_client, socket_client_2, socket_client_3 = await get_players(3)
    await base_helper(
        socket_client,
        "bet_status",
        "place_bet",
        {"amount": 10, "bet_type": "bet", "seat_number": 3},
    )
    await base_helper(
        socket_client_2,
        "bet_status",
        "place_bet",
        {"amount": 10, "bet_type": "bet", "seat_number": 5},
    )

    await base_helper(
        socket_client_3,
        "bet_status",
        "place_bet",
        {"amount": 10, "bet_type": "bet", "seat_number": 7},
    )

    await scan_multiple_cards(["1TS", "1KD", "2TH", "13S", "1AD", "1AS", "15S"])

    await base_helper(
        socket_client_3,
        "scan_dealer_card",
        "make_action",
        {"round_id": TEST_ROUND_ID, "action_type": "stand"},
    )

    game_player_1: GamePlayer = await GamePlayer.find_one({"seat_number": 3})
    assert game_player_1.making_decision is False
    assert game_player_1.player_turn is False

    game_player_2: GamePlayer = await GamePlayer.find_one({"seat_number": 5})
    assert game_player_2.making_decision is False
    assert game_player_2.player_turn is False

    game_player_3: GamePlayer = await GamePlayer.find_one({"seat_number": 7})
    assert game_player_3.making_decision is False
    assert game_player_3.player_turn is False
    await socket_client.disconnect()
    await socket_client_2.disconnect()
    await socket_client_3.disconnect()


@pytest.mark.asyncio
async def test_skip_to_dealer_when_last_2_players_have_bj(base_client):
    """
    FIRST_PLAYER: init score: 15
    SECOND_PLAYER: init score: 21
    THIRD_PLAYER: init score: 21
    FINALLY  last 2 players should be skipped, we should get scan dealer card event which means round is finished
    """
    socket_client, socket_client_2, socket_client_3 = await get_players(3)
    await base_helper(
        socket_client,
        "bet_status",
        "place_bet",
        {"amount": 10, "bet_type": "bet", "seat_number": 3},
    )
    await base_helper(
        socket_client_2,
        "bet_status",
        "place_bet",
        {"amount": 10, "bet_type": "bet", "seat_number": 5},
    )

    await base_helper(
        socket_client_3,
        "bet_status",
        "place_bet",
        {"amount": 10, "bet_type": "bet", "seat_number": 7},
    )

    await scan_multiple_cards(["2TH", "1KD", "1TS", "13S", "15S", "1AS", "1AD"])

    await base_helper(
        socket_client,
        "scan_dealer_card",
        "make_action",
        {"round_id": TEST_ROUND_ID, "action_type": "stand"},
    )

    game_player_1: GamePlayer = await GamePlayer.find_one({"seat_number": 3})
    assert game_player_1.making_decision is False
    assert game_player_1.player_turn is False

    game_player_2: GamePlayer = await GamePlayer.find_one({"seat_number": 5})
    assert game_player_2.making_decision is False
    assert game_player_2.player_turn is False

    game_player_3: GamePlayer = await GamePlayer.find_one({"seat_number": 7})
    assert game_player_3.making_decision is False
    assert game_player_3.player_turn is False
    await socket_client.disconnect()
    await socket_client_2.disconnect()
    await socket_client_3.disconnect()
