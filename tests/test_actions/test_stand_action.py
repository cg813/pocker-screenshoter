import pytest

from apps.game.documents import GamePlayer, GameRound
from tests.helpers import TEST_ROUND_ID, base_helper, get_players, scan_multiple_cards


@pytest.mark.asyncio
async def test_stand_action(base_client):
    (socket_client,) = await get_players(1)
    await base_helper(
        socket_client,
        "bet_status",
        "place_bet",
        {"amount": 10, "bet_type": "bet", "seat_number": 1},
    )
    await scan_multiple_cards(["19S", "14C", "14D"])
    data = await base_helper(
        socket_client,
        "scan_dealer_card",
        "make_action",
        {"round_id": TEST_ROUND_ID, "action_type": "stand"},
    )
    assert data == {}
    game_player = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    game_round = await GameRound.find_one({})
    assert game_round.finished_dealing is True
    assert game_player.last_action == "stand"
    assert game_player.making_decision is False
    assert game_player.player_turn is False
    await socket_client.disconnect()


@pytest.mark.asyncio
async def test_stand_action_with_incorrect_cards(base_client):
    (socket_client,) = await get_players(1)
    await base_helper(
        socket_client,
        "bet_status",
        "place_bet",
        {"amount": 10, "bet_type": "bet", "seat_number": 1},
    )
    await scan_multiple_cards(["1TS", "14C", "1AD"])
    data = await base_helper(
        socket_client,
        "error",
        "make_action",
        {"round_id": TEST_ROUND_ID, "action_type": "stand"},
    )
    assert data == {"message": "Can not find game player or it is not your turn"}
    await socket_client.disconnect()
