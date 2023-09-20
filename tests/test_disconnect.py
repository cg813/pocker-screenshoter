import pytest
from apps.game.documents import GamePlayer
import asyncio

from .helpers import get_players, base_helper


@pytest.mark.asyncio
async def test_player_disconnect(base_client):
    player_1, player_2 = await get_players(2)
    await base_helper(
        player_1,
        "bet_status",
        "place_bet",
        {"amount": 10, "bet_type": "bet", "seat_number": 1},
    )
    await base_helper(
        player_2,
        "bet_status",
        "place_bet",
        {"amount": 10, "bet_type": "bet", "seat_number": 3},
    )

    await player_1.disconnect()
    await player_2.disconnect()

    await asyncio.sleep(0.5)
    game_player_1 = await GamePlayer.find_one({"seat_number": 1})
    game_player_2 = await GamePlayer.find_one({"seat_number": 3})
    assert game_player_1.is_active is False
    assert game_player_2.is_active is False
