import pytest
from bson import ObjectId
from apps.game.documents import GamePlayer, GameRound
from apps.game.cards.base_card_manager import BaseCardManager
from apps.game.cards.actions_card_manager import ActionCardManager
from tests.helpers import (
    TEST_SESSION_DATA,
    TEST_ROUND_ID,
    base_helper,
    get_players,
    scan_multiple_cards,
    base_listener,
)


@pytest.mark.asyncio
async def test_play_one_round_with_two_players(base_client):
    """
    FIRST_PLAYER: init score: 8 -> HIT -> score: 15 -> HIT -> score: 19 -> STAND
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
    await scan_multiple_cards(["12C", "14C", "19S", "16S", "18S"])
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
        {"round_id": TEST_ROUND_ID, "card": "17D"},
    )
    first_game_player = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    assert first_game_player.player_turn is True
    assert first_game_player.making_decision is True
    assert first_game_player.last_action == "hit"
    assert first_game_player.cards == ["12C", "16S", "17D"]
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
        {"round_id": TEST_ROUND_ID, "card": "14D"},
    )
    first_game_player = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    assert first_game_player.player_turn is True
    assert first_game_player.making_decision is True
    assert first_game_player.last_action == "hit"
    assert first_game_player.cards == ["12C", "16S", "17D", "14D"]
    data = await base_helper(
        socket_client,
        "decision_maker",
        "make_action",
        {"round_id": TEST_ROUND_ID, "action_type": "stand"},
    )
    assert data == {"decision_timer": 15, "seat_number": 5}

    first_game_player = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    assert first_game_player.player_turn is False
    assert first_game_player.making_decision is False
    assert first_game_player.last_action == "stand"
    assert first_game_player.cards == ["12C", "16S", "17D", "14D"]
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
async def test_play_one_round_with_stand_with_two_players(base_client):
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
        {"amount": 15, "bet_type": "bet", "seat_number": 3},
    )

    data1 = await base_listener(
        scan_multiple_cards,
        "decision_maker",
        socket_client,
        ["19C", "18S", "15H", "17H", "19H"],
    )
    data2 = await base_helper(
        socket_client,
        "decision_maker",
        "make_action",
        {"round_id": TEST_ROUND_ID, "action_type": "stand"},
    )
    assert data2["seat_number"] == 3
    first_game_player = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    assert first_game_player.player_turn is False
    assert first_game_player.making_decision is False
    assert first_game_player.last_action == "stand"
    assert first_game_player.cards == ["19C", "17H"]
    await base_helper(
        socket_client_2,
        "scan_dealer_card",
        "make_action",
        {"round_id": TEST_ROUND_ID, "action_type": "stand"},
    )
    first_game_player = await GamePlayer.find_one(GamePlayer.seat_number == 3)
    assert first_game_player.player_turn is False
    assert first_game_player.making_decision is False
    assert first_game_player.last_action == "stand"
    assert first_game_player.cards == ["18S", "19H"]
    await socket_client.disconnect()
    await socket_client_2.disconnect()


@pytest.mark.asyncio
async def test_play_one_round_with_stand_and_hit_with_two_players(base_client):
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
        {"amount": 15, "bet_type": "bet", "seat_number": 3},
    )
    data1 = await base_listener(
        scan_multiple_cards,
        "decision_maker",
        socket_client,
        ["19C", "18S", "15H", "17H", "19H"],
    )
    assert data1 == {"seat_number": 1, "decision_timer": 15}

    data2 = await base_helper(
        socket_client,
        "decision_maker",
        "make_action",
        {"round_id": TEST_ROUND_ID, "action_type": "stand"},
    )
    assert data2 == {"decision_timer": 15, "seat_number": 3}
    first_game_player = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    assert first_game_player.player_turn is False
    assert first_game_player.making_decision is False
    assert first_game_player.last_action == "stand"
    assert first_game_player.cards == ["19C", "17H"]
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
        {"round_id": TEST_ROUND_ID, "card": "17D"},
    )
    second_game_player = await GamePlayer.find_one(GamePlayer.seat_number == 3)
    assert second_game_player.player_turn is False
    assert second_game_player.making_decision is False
    assert second_game_player.last_action == "hit"
    assert second_game_player.cards == ["18S", "19H", "17D"]
    await socket_client.disconnect()
    await socket_client_2.disconnect()


@pytest.mark.asyncio
async def test_bust_players(base_client):
    """
    FIRST_PLAYER: init score: 13 -> HIT -> score: 22 -> BUST
    SECOND_PLAYER: init score: 20 -> STAND
    THIRD_PLAYER: init score: 14 -> HIT -> score: 22 -> BUST
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
    await scan_multiple_cards(["19S", "1TD", "1TS", "17D", "14S", "1TC", "14D"])
    await base_helper(
        socket_client,
        "player_action",
        "make_action",
        {"round_id": TEST_ROUND_ID, "action_type": "hit"},
    )
    await base_helper(
        socket_client,
        "decision_maker",
        "action_cards",
        {"round_id": TEST_ROUND_ID, "card": "19D"},
    )

    first_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.seat_number == 3
    )
    assert first_game_player.player_turn is False
    assert first_game_player.making_decision is False
    assert first_game_player.last_action == "hit"
    assert first_game_player.cards == ["19S", "14S", "19D"]

    await base_helper(
        socket_client_2,
        "decision_maker",
        "make_action",
        {"round_id": TEST_ROUND_ID, "action_type": "stand"},
    )
    second_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.seat_number == 5
    )
    assert second_game_player.player_turn is False
    assert second_game_player.making_decision is False
    assert second_game_player.last_action == "stand"
    assert second_game_player.cards == ["1TD", "1TC"]
    await base_helper(
        socket_client_3,
        "player_action",
        "make_action",
        {"round_id": TEST_ROUND_ID, "action_type": "hit"},
    )
    await base_helper(
        socket_client_3,
        "scan_dealer_card",
        "action_cards",
        {"round_id": TEST_ROUND_ID, "card": "19D"},
    )

    third_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.seat_number == 7
    )

    assert third_game_player.player_turn is False
    assert third_game_player.making_decision is False
    assert third_game_player.last_action == "hit"
    assert third_game_player.cards == ["1TS", "14D", "19D"]
    await socket_client.disconnect()
    await socket_client_2.disconnect()
    await socket_client_3.disconnect()


@pytest.mark.asyncio
async def test_21_with_two_players(base_client):
    """
    FIRST_PLAYER: init score: 21
    SECOND_PLAYER: init score: 21
    FINALLY we should get scan dealer card event which means round is finished
    """
    socket_client, socket_client_2 = await get_players(2)
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

    await scan_multiple_cards(["1TS", "1KD", "13S", "1AD", "1AS"])

    game_player_1: GamePlayer = await GamePlayer.find_one({"seat_number": 3})
    assert game_player_1.making_decision is False
    assert game_player_1.player_turn is False

    game_player_2: GamePlayer = await GamePlayer.find_one({"seat_number": 5})
    assert game_player_2.making_decision is False
    assert game_player_2.player_turn is False
    await socket_client.disconnect()
    await socket_client_2.disconnect()


@pytest.mark.asyncio
async def test_move_to_next_player_on_21(base_client):
    player_1, player_2 = await get_players(2)
    await base_helper(
        player_1,
        "bet_status",
        "place_bet",
        {"amount": 10, "bet_type": "bet", "seat_number": 3},
    )
    await base_helper(
        player_2,
        "bet_status",
        "place_bet",
        {"amount": 10, "bet_type": "bet", "seat_number": 5},
    )
    await scan_multiple_cards(["1AC", "15S", "17D", "1TS", "18D"])
    game_player_2: GamePlayer = await GamePlayer.find_one({"seat_number": 5})
    assert game_player_2.making_decision is True
    assert game_player_2.player_turn is True
    game_player_1: GamePlayer = await GamePlayer.find_one({"seat_number": 3})
    assert game_player_1.player_turn is False
    assert game_player_1.making_decision is False
    await player_1.disconnect()
    await player_2.disconnect()


@pytest.mark.asyncio
async def test_play_one_round_with_two_players_skip_dealer_scan(base_client):
    """
    FIRST_PLAYER: init score: 18 -> HIT -> score: 25
    SECOND_PLAYER: init score: 16 -> HIT -> score: 23
    round is finished, dealer doesn't need to scan card
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
    await scan_multiple_cards(["19C", "18C", "19S", "29S", "18S"])
    await base_helper(
        socket_client,
        "player_action",
        "make_action",
        {"round_id": TEST_ROUND_ID, "action_type": "hit"},
    )
    await base_helper(
        socket_client,
        "decision_maker",
        "action_cards",
        {"round_id": TEST_ROUND_ID, "card": "17D"},
    )
    first_game_player = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    assert first_game_player.last_action == "hit"
    assert first_game_player.cards == ["19C", "29S", "17D"]
    await base_helper(
        socket_client_2,
        "player_action",
        "make_action",
        {"round_id": TEST_ROUND_ID, "action_type": "hit"},
    )
    await base_helper(
        socket_client_2,
        "",
        "action_cards",
        {"round_id": TEST_ROUND_ID, "card": "27D"},
    )
    second_game_player = await GamePlayer.find_one(GamePlayer.seat_number == 5)
    assert second_game_player.last_action == "hit"
    assert second_game_player.cards == ["18C", "18S", "27D"]
    card_manager = BaseCardManager(TEST_SESSION_DATA, TEST_ROUND_ID)
    card_manager.round_id = first_game_player.game_round
    card_manager.game_id = first_game_player.game_id
    card_manager.game_player = first_game_player
    card_manager.next_game_player = second_game_player
    await card_manager.move_to_next_player()
    game_round = await GameRound.get_motor_collection().find_one(
        {
            "_id": ObjectId(first_game_player.game_round),
            "game_id": first_game_player.game_id,
        }
    )
    assert len(game_round["dealer_cards"]) == 1
    assert game_round["finished_dealing"] is True
    assert game_round["finished"] is False
    await socket_client.disconnect()
    await socket_client_2.disconnect()


@pytest.mark.asyncio
async def test_play_one_round_skip_dealer_scan_after_all_players_have_BJ(base_client):
    """
    FIRST_PLAYER: BJ
    SECOND_PLAYER: BJ
    round is not finished, dealer has A and have to scan another card
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
    await scan_multiple_cards(["1TC", "1TH", "1TS", "2AC", "1AH"])
    first_game_player = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    assert first_game_player.cards == ["1TC", "2AC"]
    second_game_player = await GamePlayer.find_one(GamePlayer.seat_number == 5)
    assert second_game_player.cards == ["1TH", "1AH"]
    action_card_manager = ActionCardManager(TEST_SESSION_DATA, TEST_ROUND_ID)
    await action_card_manager.scan_dealer_card("12H")
    game_round = await GameRound.get_motor_collection().find_one(
        {
            "_id": ObjectId(first_game_player.game_round),
            "game_id": first_game_player.game_id,
        }
    )
    assert len(game_round["dealer_cards"]) == 2
    assert game_round["finished_dealing"] is True
    assert game_round["finished"] is False
    await socket_client.disconnect()
    await socket_client_2.disconnect()
