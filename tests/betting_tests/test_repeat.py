import json

import pytest

from bson import ObjectId

from apps.connections import redis_cache
from apps.game.documents import GamePlayer, GameRound
from apps.game.services.custom_exception import ValidationError
from tests.helpers import (
    TEST_GAME_ID,
    TEST_SESSION_DATA,
    TEST_MERCHANT_ID,
    TEST_DEPOSIT,
)


@pytest.mark.asyncio
async def test_make_repeat(betting_manager):
    prev_round_id = str(ObjectId())
    game_round: GameRound = await GameRound.find_one(GameRound.game_id == TEST_GAME_ID)
    game_round.prev_round_id = prev_round_id
    await game_round.save()
    await redis_cache.redis_cache.set(
        f"{TEST_SESSION_DATA['user_id']}:{TEST_MERCHANT_ID}:{prev_round_id}",
        json.dumps(
            {
                1: {
                    "bet": 30,
                    "bet_list": [10, 10, 10],
                    "bet_21_3": 0,
                    "bet_21_3_list": [],
                    "bet_perfect_pair": 0,
                    "bet_perfect_pair_list": [],
                }
            }
        ),
    )

    await betting_manager.make_repeat(TEST_SESSION_DATA)

    updated_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.game_id == TEST_GAME_ID
    )

    assert updated_game_player.bet == 30
    assert updated_game_player.bet_list == [10, 10, 10]
    assert updated_game_player.deposit == TEST_DEPOSIT - 30


@pytest.mark.asyncio
async def test_make_repeat_with_side_bets(betting_manager):
    prev_round_id = str(ObjectId())
    game_round: GameRound = await GameRound.find_one(GameRound.game_id == TEST_GAME_ID)
    game_round.prev_round_id = prev_round_id
    await game_round.save()
    await redis_cache.redis_cache.set(
        f"{TEST_SESSION_DATA['user_id']}:{TEST_MERCHANT_ID}:{prev_round_id}",
        json.dumps(
            {
                1: {
                    "bet": 30,
                    "bet_list": [10, 10, 10],
                    "bet_21_3": 15,
                    "bet_21_3_list": [5, 10],
                    "bet_perfect_pair": 20,
                    "bet_perfect_pair_list": [5, 5, 10],
                }
            }
        ),
    )

    await betting_manager.make_repeat(TEST_SESSION_DATA)

    updated_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.game_id == TEST_GAME_ID
    )

    assert updated_game_player.bet == 30
    assert updated_game_player.bet_list == [10, 10, 10]
    assert updated_game_player.bet_21_3 == 15
    assert updated_game_player.bet_21_3_list == [5, 10]
    assert updated_game_player.bet_perfect_pair == 20
    assert updated_game_player.bet_perfect_pair_list == [5, 5, 10]
    assert updated_game_player.deposit == TEST_DEPOSIT - 65


@pytest.mark.asyncio
async def test_make_repeat_with_no_cached_data(betting_manager):
    with pytest.raises(ValidationError) as error:
        await betting_manager.make_repeat(TEST_SESSION_DATA)
        assert str(error) == "can't make repeat"


@pytest.mark.asyncio
async def test_make_repeat_with_insufficient_funds(betting_manager):
    prev_round_id = str(ObjectId())
    game_round: GameRound = await GameRound.find_one(GameRound.game_id == TEST_GAME_ID)
    game_round.prev_round_id = prev_round_id
    await game_round.save()
    await redis_cache.redis_cache.set(
        f"{TEST_SESSION_DATA['user_id']}:{TEST_MERCHANT_ID}:{prev_round_id}",
        json.dumps(
            {
                1: {
                    "bet": 40,
                    "bet_list": [10, 10, 20],
                    "bet_21_3": 0,
                    "bet_21_3_list": [],
                    "bet_perfect_pair": 0,
                    "bet_perfect_pair_list": [],
                }
            }
        ),
    )
    await redis_cache.set_user_balance_in_cache(
        TEST_SESSION_DATA["user_id"], TEST_MERCHANT_ID, 0
    )

    with pytest.raises(ValidationError) as error:
        await betting_manager.make_repeat(TEST_SESSION_DATA)
        assert str(error) == "not enough funds to make repeat"


@pytest.mark.asyncio
async def test_make_repeat_after_making_repeat(betting_manager):
    prev_round_id = str(ObjectId())
    game_round: GameRound = await GameRound.find_one(GameRound.game_id == TEST_GAME_ID)
    game_round.prev_round_id = prev_round_id
    await game_round.save()
    await redis_cache.redis_cache.set(
        f"{TEST_SESSION_DATA['user_id']}:{TEST_MERCHANT_ID}:{prev_round_id}",
        json.dumps(
            {
                1: {
                    "bet": 30,
                    "bet_list": [10, 10, 10],
                    "bet_21_3": 0,
                    "bet_21_3_list": [],
                    "bet_perfect_pair": 0,
                    "bet_perfect_pair_list": [],
                }
            }
        ),
    )

    await betting_manager.make_repeat(TEST_SESSION_DATA)

    with pytest.raises(ValidationError) as error:
        await betting_manager.make_repeat(TEST_SESSION_DATA)
        assert str(error) == "Repeat is already made"
