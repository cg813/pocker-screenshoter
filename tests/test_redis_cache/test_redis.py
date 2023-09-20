import json

import pytest
from bson import ObjectId

from apps.connections import redis_cache
from apps.game.documents import GameRound
from apps.game.services.custom_exception import ValidationError
from apps.game.services.utils import get_timestamp
from tests.helpers import TEST_GAME_ID, TEST_MERCHANT_ID, TEST_ROUND_ID


@pytest.mark.asyncio
async def test_setting_value():
    await redis_cache.set("test_key", "test_value")
    cache_value = await redis_cache.get("test_key")

    assert cache_value == "test_value"


@pytest.mark.asyncio
async def test_get_repeat_data():
    test_data = {"bet": 10, "bet_list": [10]}
    await redis_cache.redis_cache.setex("1:1:1", 10, json.dumps(test_data))

    cache_data = await redis_cache.get_repeat_data("1:1:1")
    assert test_data == cache_data


@pytest.mark.asyncio
async def test_get_or_cache_game_player_seats():
    await redis_cache.set(f"{TEST_ROUND_ID}:seats", json.dumps([1, 2, 3]))
    cache_data = await redis_cache.get_or_cache_game_player_seats(TEST_ROUND_ID)
    assert cache_data == [1, 2, 3]


@pytest.mark.asyncio
async def test_get_or_cache_game_player_seats_without_any_data():
    cache_data = await redis_cache.get_or_cache_game_player_seats(TEST_ROUND_ID)
    assert cache_data == []


@pytest.mark.asyncio
async def test_get_or_cache_game_player_seats_taking_from_gameplayers(betting_manager):
    data = await betting_manager.charge_user(amount=10, seat_number=1)
    cache_data = await redis_cache.get_or_cache_game_player_seats(TEST_ROUND_ID)
    assert cache_data == [data.get("seat_number")]


@pytest.mark.asyncio
async def test_get_or_cache_merchant():
    test_data = {"games": [], "transaction_url": "test", "validate_token_url": "test"}
    await redis_cache.set(f"{TEST_MERCHANT_ID}:{TEST_GAME_ID}", json.dumps(test_data))
    cache_data = await redis_cache.get_or_cache_merchant(TEST_MERCHANT_ID, TEST_GAME_ID)
    assert cache_data == test_data


@pytest.mark.asyncio
async def test_get_or_cache_merchant_with_data_in_db():
    cache_data = await redis_cache.get_or_cache_merchant(TEST_MERCHANT_ID, TEST_GAME_ID)

    assert "transaction_url" in cache_data
    assert "validate_token_url" in cache_data
    assert "bet_range" in cache_data
    assert "decision_make_time" in cache_data
    assert "game_name" in cache_data
    assert "min_bet" in cache_data
    assert "max_bet" in cache_data
    assert "is_active" in cache_data
    assert cache_data.get("game_id") == TEST_GAME_ID


@pytest.mark.asyncio
async def test_get_or_cache_merchant_without_any_data_in_db_and_cache():
    random_merchant_id = str(ObjectId())
    random_game_id = str(ObjectId())
    with pytest.raises(ValidationError) as error:
        await redis_cache.get_or_cache_merchant(random_merchant_id, random_game_id)
        assert str(error) == f"Can not find game with id '{random_game_id}'"


@pytest.mark.asyncio
async def test_set_user_balance_in_cache():
    await redis_cache.set_user_balance_in_cache(1, TEST_MERCHANT_ID, 100)
    cache_data = await redis_cache.get(f"1:{TEST_MERCHANT_ID}")
    assert cache_data == "100"


@pytest.mark.asyncio
async def test_take_seat_when_seat_is_available():
    await redis_cache.take_seat(TEST_GAME_ID, 1, TEST_MERCHANT_ID, 1, TEST_ROUND_ID)
    cache_data = await redis_cache.get(f"{TEST_GAME_ID}:1")
    assert cache_data == f"1:{TEST_MERCHANT_ID}"


@pytest.mark.asyncio
async def test_take_seat_when_seat_is_taken():
    await redis_cache.take_seat(TEST_GAME_ID, 1, TEST_MERCHANT_ID, 1, TEST_ROUND_ID)
    with pytest.raises(ValidationError) as error:
        await redis_cache.take_seat(TEST_GAME_ID, 1, TEST_MERCHANT_ID, 2, TEST_ROUND_ID)
        assert str(error) == "Seat is already taken."


@pytest.mark.asyncio
async def test_take_seat_when_seat_was_taken_in_previous_round():
    await redis_cache.take_seat(TEST_GAME_ID, 1, TEST_MERCHANT_ID, 1, TEST_GAME_ID)
    with pytest.raises(ValidationError) as error:
        await redis_cache.take_seat(TEST_ROUND_ID, 1, TEST_MERCHANT_ID, 2, TEST_GAME_ID)
        assert str(error) == "Seat is locked for the previous player."


@pytest.mark.asyncio
async def test_set_round_start_timestamp_in_cache_when_no_data_in_cache():
    await GameRound.get_motor_collection().insert_one(
        {
            "_id": ObjectId("5349b4ddd2781d08c09890f4"),
            "created_at": get_timestamp(),
            "updated_at": get_timestamp(),
            "card_count": 0,
            "game_id": TEST_GAME_ID,
            "round_id": "Test_round",
            "start_timestamp": get_timestamp(15),
            "dealer_cards": [],
            "was_reset": False,
            "finished": False,
            "dealer_name": "",
        }
    )

    start_data = await redis_cache.get_or_cache_round_start_timestamp(
        "5349b4ddd2781d08c09890f4"
    )
    redis_start_data = await redis_cache.get("5349b4ddd2781d08c09890f4:start_timestamp")
    assert str(start_data) == redis_start_data


@pytest.mark.asyncio
async def test_set_round_start_timestamp_in_cache_when_data_in_cache():
    game_round_id = "5349b4ddd2781d08c09890f4"
    timestamp = "54212431"
    await redis_cache.set(f"{game_round_id}:start_timestamp", timestamp)
    start_data = await redis_cache.get_or_cache_round_start_timestamp(game_round_id)
    assert str(start_data) == timestamp


@pytest.mark.asyncio
async def test_set_round_start_timestamp_in_cache_when_no_data_in_db_and_cache():
    game_round_id = "5349b4ddd2781d08c09890f4"
    with pytest.raises(ValidationError) as error:
        await redis_cache.get_or_cache_round_start_timestamp(game_round_id)
        assert str(error) == "Can not find round with id '5349b4ddd2781d08c09890f4'"
