import pytest

from apps.game.documents import GamePlayer, GameRound
from apps.connections import redis_cache
from tests.helpers import TEST_ROUND_ID, base_helper, get_players, scan_multiple_cards


# @pytest.mark.asyncio
# async def test_split_action(base_client):
#     (socket_client,) = await get_players(1)
#     await base_helper(
#         socket_client,
#         "bet_status",
#         "place_bet",
#         {"amount": 10, "bet_type": "bet", "seat_number": 1},
#     )
#     await scan_multiple_cards(["58S", "55S", "68C"])
#     data = await base_helper(
#         socket_client,
#         "player_action",
#         "make_action",
#         {"round_id": TEST_ROUND_ID, "action_type": "split"},
#     )

#     game_player: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 1)
#     game_player_2: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 2)
#     assert game_player.cards == ["58S"]
#     assert game_player_2.cards == ["68C"]
#     assert game_player.last_action == "split:1"
#     assert game_player.seat_number == 1
#     assert game_player_2.seat_number == 2
#     assert game_player.last_action
#     game_round = await GameRound.find_one({})

#     data = await base_helper(
#         socket_client,
#         "send_hand_value",
#         "action_cards",
#         {"round_id": TEST_ROUND_ID, "card": "55S"},
#     )

#     game_player: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 1)

#     assert game_player.cards == ["58S", "55S"]
#     assert game_player.last_action == "split:2"

#     data = await base_helper(
#         socket_client,
#         "make_decision",
#         "action_cards",
#         {"round_id": TEST_ROUND_ID, "card": "66S"},
#     )

#     game_player: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 2)
#     assert game_player.cards == ["68C", "66S"]
#     seats = await redis_cache.get_or_cache_game_player_seats(TEST_ROUND_ID)
#     assert seats == [1, 2]
