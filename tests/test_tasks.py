import pytest
import requests

from beanie import PydanticObjectId

from apps.game.documents import GamePlayer, GameRound
from apps.connections import redis_cache
from apps.game.tasks import (
    send_bet_to_merchant_and_update_game_player,
    start_new_round,
)
from tests.helpers import mock_request, mock_bad_request, TEST_GAME_ID, TEST_ROUND_ID


@pytest.mark.asyncio
async def test_send_bet_to_merchant(monkeypatch, betting_manager):
    monkeypatch.setattr(requests, "post", mock_request)
    await betting_manager.charge_user(10, 1)
    game_player = await GamePlayer.get_motor_collection().find_one({"seat_number": 1})
    game_player["_id"] = str(game_player["_id"])
    send_bet_to_merchant_and_update_game_player("http://testurl", game_player, "snake")
    cached_balance = await redis_cache.get(
        f"{game_player['user_id']}:{game_player['merchant']}"
    )
    assert float(cached_balance) == 980


@pytest.mark.asyncio
async def test_send_bet_to_merchant_when_merchant_rejects_request(
    monkeypatch, betting_manager
):
    monkeypatch.setattr(requests, "post", mock_bad_request)
    await betting_manager.charge_user(52, 1)
    game_player: dict = await GamePlayer.get_motor_collection().find_one(
        {"seat_number": 1}
    )
    game_player["_id"] = str(game_player["_id"])
    send_bet_to_merchant_and_update_game_player("http://testurl", game_player, "snake")
    game_player: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    cached_balance = await redis_cache.get(
        f"{game_player.user_id}:{game_player.merchant}"
    )
    assert float(cached_balance) == 980
    assert game_player.archived is True
    assert game_player.rejected is True
    assert game_player.detail == "insufficient_balance"


@pytest.mark.asyncio
async def test_start_new_round_task():
    start_new_round(TEST_GAME_ID)
    previous_round = await GameRound.get(PydanticObjectId(TEST_ROUND_ID))
    assert previous_round.finished is True
    new_game_round: GameRound = await GameRound.find_one({"finished": False})
    assert new_game_round.start_timestamp is None
    assert new_game_round.created_at is not None
    assert new_game_round.updated_at is not None
    data = dict(new_game_round)
    del data["id"]
    del data["revision_id"]
    del data["created_at"]
    del data["updated_at"]
    del data["start_timestamp"]
    del data["round_id"]

    assert data == {
        "card_count": 0,
        "game_id": TEST_GAME_ID,
        "dealer_cards": [],
        "show_dealer_cards": False,
        "finished_dealing": False,
        "winner": None,
        "was_reset": False,
        "finished": False,
        "dealer_name": None,
        "insurance_timestamp": None,
        "prev_round_id": None,
    }
