import json

import pytest

from bson import ObjectId

from apps.connections import redis_cache
from apps.game.documents import GamePlayer, GameRound
from apps.game.services.connect_manager import ConnectManager

from ..helpers import (
    TEST_GAME_ID,
    TEST_SESSION_DATA,
    TEST_MERCHANT_ID,
    TEST_DEPOSIT,
    base_helper,
    connect_socket,
    mock_check_if_user_can_connect,
)


@pytest.mark.asyncio
async def test_make_repeat(monkeypatch):
    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )

    _, client = await connect_socket(TEST_GAME_ID, "test_sid")
    prev_round_id = str(ObjectId())
    game_round: GameRound = await GameRound.find_one(GameRound.game_id == TEST_GAME_ID)
    game_round.prev_round_id = prev_round_id
    await game_round.save()
    await redis_cache.redis_cache.set(
        f"{TEST_SESSION_DATA['user_id']}:{TEST_MERCHANT_ID}:{prev_round_id}",
        json.dumps(
            {
                1: {
                    "bet": 50,
                    "bet_list": [20, 20, 10],
                    "bet_21_3": 0,
                    "bet_21_3_list": [],
                    "bet_perfect_pair": 0,
                    "bet_perfect_pair_list": [],
                }
            }
        ),
    )

    await base_helper(client, "repeat_status", "make_repeat", _)
    updated_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.game_id == TEST_GAME_ID
    )

    assert updated_game_player.bet == 50
    assert updated_game_player.bet_list == [20, 20, 10]
    assert updated_game_player.deposit == TEST_DEPOSIT - 50
    await client.disconnect()
