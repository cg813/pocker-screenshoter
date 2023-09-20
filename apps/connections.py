import json
from typing import Optional

from aioredis import Redis, from_url
from bson import ObjectId

from apps.game.documents import GamePlayer, GameRound, Merchant, Game
from apps.game.services.custom_exception import ValidationError

from .config import settings


class RedisCache:
    def __init__(self):
        self.redis_cache: Optional[Redis] = None

    async def init_cache(self):
        self.redis_cache = await from_url(
            settings.REDIS_CACHE_URL, encoding="utf-8", decode_responses=True
        )

    async def set(self, key, value):
        return await self.redis_cache.execute_command(
            "set", key, value, "ex", settings.REDIS_CACHE_EXPIRATION_TIME
        )

    async def get(self, key):
        return await self.redis_cache.get(key)

    async def set_expire(self, key, value, time=900):
        return await self.redis_cache.execute_command("set", key, value, "ex", time)

    async def get_repeat_data(self, key) -> dict:
        repeat_data = await self.redis_cache.get(key)
        if repeat_data:
            return json.loads(repeat_data)
        raise ValidationError("can't make repeat")

    async def get_or_cache_game_player_seats(self, game_round_id: str) -> list:
        if players_seat_numbers := await self.redis_cache.get(f"{game_round_id}:seats"):
            return json.loads(players_seat_numbers)
        game_players = (
            GamePlayer.get_motor_collection()
            .find({"game_round": game_round_id})
            .sort("seat_number")
        )
        seats = []
        for player in await game_players.to_list(14):
            if player["bet"] > 0:
                seats.append(player["seat_number"])
        await self.redis_cache.set(f"{game_round_id}:seats", json.dumps(seats))
        return seats

    async def get_or_cache_game_type(self, game_id: str) -> str:
        if game_type := await self.redis_cache.get(f"{game_id}:type"):
            return json.loads(game_type)
        game = (
            await Game.get_motor_collection()
            .find({"_id": ObjectId(game_id)})
            .to_list(1)
        )
        game_type = game[0]["type"]
        await self.redis_cache.set(f"{game_id}:type", json.dumps(game_type))
        return game_type

    async def update_cached_seats(self, game_round_id: str, seat_number: int):
        seats = await self.get_or_cache_game_player_seats(game_round_id=game_round_id)
        index = seats.index(seat_number)
        seats.insert(index + 1, seat_number + 1)
        await self.redis_cache.set(f"{game_round_id}:seats", json.dumps(seats))

    async def get_taken_seats(self, game_id: str) -> dict or None:
        if taken_seats := await self.redis_cache.get(f"{game_id}:taken_seats"):
            return json.loads(taken_seats)
        return {}

    async def get_or_cache_round_start_timestamp(self, game_round_id: str):
        if start_timestamp := await self.redis_cache.get(
            f"{game_round_id}:start_timestamp"
        ):
            return json.loads(start_timestamp)
        start_timestamp = await GameRound.get_motor_collection().find_one(
            {"_id": ObjectId(game_round_id)}, {"_id": 0, "start_timestamp": 1}
        )
        if start_timestamp:
            timestamp = start_timestamp["start_timestamp"]
            await self.redis_cache.set(f"{game_round_id}:start_timestamp", timestamp)
            return timestamp
        raise ValidationError(f"Can not find round with id '{game_round_id}'")

    async def get_or_cache_merchant(self, merchant_id: str, game_id: str):
        if merchant_data := await self.redis_cache.get(f"{merchant_id}:{game_id}"):
            return json.loads(merchant_data)
        merchant = await Merchant.get_motor_collection().find_one(
            {"_id": ObjectId(merchant_id), "games.game_id": game_id},
            {
                "games.$": 1,
                "_id": 0,
                "transaction_url": 1,
                "validate_token_url": 1,
                "schema_type": 1,
                "bet_url": 1,
                "win_url": 1,
                "rollback_url": 1,
                "get_balance_url": 1,
            },
        )
        if merchant:
            merchant_data_for_cache = merchant.get("games")[0]
            merchant_data_for_cache["transaction_url"] = merchant["transaction_url"]
            merchant_data_for_cache["get_balance_url"] = merchant["get_balance_url"]
            merchant_data_for_cache["bet_url"] = merchant["bet_url"]
            merchant_data_for_cache["win_url"] = merchant["win_url"]
            merchant_data_for_cache["rollback_url"] = merchant["rollback_url"]
            merchant_data_for_cache["validate_token_url"] = merchant[
                "validate_token_url"
            ]
            merchant_data_for_cache["schema_type"] = merchant["schema_type"]
            await self.redis_cache.set(
                f"{merchant_id}:{game_id}", json.dumps(merchant_data_for_cache)
            )
            return merchant_data_for_cache
        raise ValidationError(f"Can not find game with id '{game_id}'")

    async def get_or_cache_game(self, game_id: str):
        if game_data := await self.redis_cache.get(game_id):
            return json.loads(game_data)
        game = await Game.get_motor_collection().find_one(
            {"_id": ObjectId(game_id)},
            {"_id": 0, "table_stream_key_1": 1, "table_stream_key_2": 1, "name": 1},
        )
        await self.redis_cache.set(game_id, json.dumps(game))
        return dict(game)

    async def set_user_balance_in_cache(self, user_id: str, merchant_id, balance):
        async with self.redis_cache.pipeline(transaction=True) as pipe:
            await pipe.set(f"{user_id}:{merchant_id}", balance).execute()

    async def take_seat(
        self,
        round_id: str,
        seat_number: int,
        merchant_id: str,
        user_id: str,
        previous_round_id: str,
    ):
        async with self.redis_cache.pipeline(transaction=True) as pipe:
            seat = await self.redis_cache.get(f"{round_id}:{seat_number}")
            previous_round_seat = await self.redis_cache.get(
                f"{previous_round_id}:{seat_number}"
            )
            if seat == f"{user_id}:{merchant_id}":
                return
            elif (
                previous_round_seat
                and previous_round_seat != f"{user_id}:{merchant_id}"
            ):
                raise ValidationError("Seat is locked for the previous player.")
            elif seat is None:
                await pipe.set(
                    f"{round_id}:{seat_number}", f"{user_id}:{merchant_id}"
                ).execute()
            else:
                raise ValidationError("Seat is already taken.")

    async def clean_no_bet_seat_after_rollback(self, total_bet, round_id, seat_number):
        if total_bet == 0:
            await self.redis_cache.delete(f"{round_id}:{seat_number}")

    async def flush_db(self):
        await self.redis_cache.flushdb()

    async def close(self):
        await self.redis_cache.close()


redis_cache = RedisCache()
