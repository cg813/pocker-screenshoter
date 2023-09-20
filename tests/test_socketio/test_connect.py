import jwt
import pytest
from apps.game.services.utils import generate_token_for_stream
import socketio

from apps.game.documents import GamePlayer
from apps.game.services.connect_manager import ConnectManager
from apps.config import settings

from ..helpers import (
    TEST_DEPOSIT,
    TEST_GAME_ID,
    connect_socket,
    connect_socket_with_invalid_data,
    connect_socket_with_nonexistent_game,
    mock_check_if_user_can_connect,
    mock_check_if_user_can_connect_witch_nonexistent_game,
)


@pytest.mark.asyncio
async def test_on_connect(monkeypatch):

    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )
    data, client = await connect_socket(TEST_GAME_ID, "test_sid")
    assert "game_name" in data
    assert "card_count" in data
    assert "user_deposit" in data
    assert "starts_at" in data
    assert "total_bet" in data
    assert "min_bet" in data
    assert "max_bet" in data
    assert "bet_range" in data
    assert "round_id" in data
    assert "game_history" in data
    assert "table_stream_key_1" in data
    assert "table_stream_key_2" in data

    await client.disconnect()


@pytest.mark.asyncio
async def test_connect_with_invalid_token():
    sio = socketio.AsyncClient()

    error = await connect_socket_with_invalid_data(TEST_GAME_ID, "test_token", sio)
    assert error["message"] == "Can not identify user please try again"


@pytest.mark.asyncio
async def test_connect_to_game_which_does_not_exists(monkeypatch):
    sio = socketio.AsyncClient()

    monkeypatch.setattr(
        ConnectManager,
        "_check_if_user_can_connect",
        mock_check_if_user_can_connect_witch_nonexistent_game,
    )
    error = await connect_socket_with_nonexistent_game(
        "618e39136a419d06ecf65eb4", "test_sid", sio
    )
    assert error["message"] == "Can not find game with id '618e39136a419d06ecf65eb4'"


@pytest.mark.asyncio
async def test_on_connect_data_when_two_players_present(monkeypatch, betting_manager):
    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )

    await betting_manager.charge_user(10, 1)
    await betting_manager.charge_user(20, 3)

    on_connect_data, client = await connect_socket(TEST_GAME_ID, "test_sid")
    assert on_connect_data["seats"] == {
        "1": {
            "cards": [],
            "score": "0",
            "user_name": "test_user",
            "making_decision": False,
            "player_turn": False,
            "decision_time": 0,
            "current_player": True,
            "last_action": None,
            "player_id": "2507f1f77bcf86cd799439011",
            "insured": None,
        },
        "3": {
            "cards": [],
            "score": "0",
            "user_name": "test_user",
            "making_decision": False,
            "player_turn": False,
            "decision_time": 0,
            "current_player": True,
            "last_action": None,
            "player_id": "2507f1f77bcf86cd799439011",
            "insured": None,
        },
    }
    assert on_connect_data["chips"] == {
        "1": [
            {
                "type": "bet",
                "bet_list": [10],
                "total_bet": 10.0,
            },
            {
                "type": "bet_21_3",
                "bet_list": [],
                "total_bet": 0,
            },
            {
                "type": "bet_perfect_pair",
                "bet_list": [],
                "total_bet": 0,
            },
        ],
        "3": [
            {
                "type": "bet",
                "bet_list": [20],
                "total_bet": 20.0,
            },
            {
                "type": "bet_21_3",
                "bet_list": [],
                "total_bet": 0,
            },
            {
                "type": "bet_perfect_pair",
                "bet_list": [],
                "total_bet": 0,
            },
        ],
    }

    await client.disconnect()


@pytest.mark.asyncio
async def test_change_players_user_token_on_connect(betting_manager):

    await betting_manager.charge_user(10, 3)
    game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.game_id == TEST_GAME_ID
    )

    assert game_player.user_token == "test_token"
    assert game_player.sid == "test_sid"

    data, client = await connect_socket(TEST_GAME_ID, "test_token_2")
    game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.game_id == TEST_GAME_ID
    )
    assert game_player.user_token == "test_token_2"

    await client.disconnect()


@pytest.mark.asyncio
async def test_getting_on_connect_deposit_from_cache(betting_manager):

    await betting_manager.charge_user(10, 3)
    await GamePlayer.find_one(GamePlayer.game_id == TEST_GAME_ID)

    reconnect_data, client = await connect_socket(TEST_GAME_ID, "test_sid")
    assert reconnect_data["user_deposit"] == TEST_DEPOSIT - 10

    await client.disconnect()


@pytest.mark.asyncio
async def test_connect_dealer():
    key = jwt.encode({}, settings.SECRET_KEY)

    data, _ = await connect_socket(TEST_GAME_ID, "test_token", key)
    assert "starts_at" in data
    assert data["card_count"] == 0
    assert data["round_id"] == "Test_round"
    assert data["_round_id"] == "5349b4ddd2781d08c09890f3"
    assert data["table_stream_key_1"] == "123"
    assert data["table_stream_key_2"] == "456"
    assert data["game_state"] == "betting"
    assert data["dealer_name"] is None
    assert data["game_name"] == "test_game"
    assert data["seats"] == {}
    assert data["chips"] == {}
    assert data["dealer_cards"] == []
    assert data["dealer_score"] == "0"
    assert data["finished_dealing"] is False
    assert data["insurance_timer"] == 0
    assert data["player_count"] == "1"
    assert data["stream_authorization"] == await generate_token_for_stream(TEST_GAME_ID)
