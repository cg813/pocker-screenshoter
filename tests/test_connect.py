import pytest
import jwt

from apps.game.documents import GamePlayer
from apps.game.services.connect_manager import ConnectManager
from apps.game.services.connect_manager import DealerConnectManager
from apps.game.services.custom_exception import ValidationError
from apps.config import settings
from apps.connections import redis_cache
from apps.game.services.utils import generate_token_for_stream

from .helpers import (
    TEST_DEPOSIT,
    TEST_GAME_ID,
    mock_check_if_user_can_connect,
    mock_check_if_user_can_connect_witch_nonexistent_game,
)


@pytest.mark.asyncio
async def test_on_connect(monkeypatch):
    """A simple websocket test"""
    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )
    connect_manager = ConnectManager(TEST_GAME_ID, "test_token", "test_sid")
    data, _ = await connect_manager.connect_to_game()
    cache_data = await redis_cache.redis_cache.hgetall(connect_manager.sid)
    assert data["total_bet"] == 0
    assert data["dealer_name"] is None
    assert data["user_deposit"] == 100092.0
    assert data["min_bet"] == 10.0
    assert data["max_bet"] == 200.0
    assert data["bet_range"] == [5.0, 10.0, 20.0, 50.0]
    assert data["game_name"] == "test_game"
    assert data["user_name"] == "test_user"
    assert data["user_id"] == 2
    assert data["game_history"] == []
    assert data["can_make_repeat"] is False
    assert "starts_at" in data
    assert data["card_count"] == 0
    assert data["round_id"] == "Test_round"
    assert data["_round_id"] == "5349b4ddd2781d08c09890f3"
    assert data["table_stream_key_1"] == "123"
    assert data["table_stream_key_2"] == "456"
    assert data["game_state"] == "betting"
    assert data["seats"] == {}
    assert data["chips"] == {}
    assert data["dealer_cards"] == []
    assert data["dealer_score"] == "0"
    assert data["player_id"] == cache_data["user_id"] + cache_data["merchant_id"]
    assert data["insurance_timer"] == 0
    assert data["insurable_seats"] == []
    assert data["player_count"] is None
    assert data["stream_authorization"] == await generate_token_for_stream(
        cache_data["game_id"]
    )


@pytest.mark.asyncio
async def test_connect_with_invalid_token():
    """
    GIVEN
    WHEN user tries to connect with expired token
    THEN server should reject request and return appropriate message
    """
    connect_manager = ConnectManager(TEST_GAME_ID, "test_token", "test_sid")
    with pytest.raises(ValidationError) as error:
        await connect_manager.connect_to_game()
        assert str(error) == "Can not identify user please try again"


@pytest.mark.asyncio
async def test_connect_game_which_does_not_exists(monkeypatch):
    """
    GIVEN
    WHEN user tries to connect with game_id which does not exists or is deleted
    THEN server should return appropriate message
    """
    monkeypatch.setattr(
        ConnectManager,
        "_check_if_user_can_connect",
        mock_check_if_user_can_connect_witch_nonexistent_game,
    )
    connect_manager = ConnectManager(
        "618e39136a419d06ecf65eb4", "test_token", "test_sid"
    )
    with pytest.raises(ValidationError) as error:
        await connect_manager.connect_to_game()
        assert str(error) == "Can not find game with id '618e39136a419d06ecf65eb4'"


@pytest.mark.asyncio
async def test_on_connect_data_when_two_players_present(monkeypatch, betting_manager):
    """
    GIVEN: we have an user that can connect and bet to the game
    WHEN: user connects and places bets on two separate boxes and reconnects
    THEN: on reconnect, in data there should be description of game players
    """
    await betting_manager.charge_user(10, 1)
    await betting_manager.charge_user(10, 3)

    connect_manager = ConnectManager(
        game_id=TEST_GAME_ID, user_token="test_token", sid="test_sid"
    )
    on_connect_data, _ = await connect_manager.connect_to_game()
    assert on_connect_data["seats"] == {
        1: {
            "cards": [],
            "making_decision": False,
            "player_turn": False,
            "score": "0",
            "user_name": "test_user",
            "current_player": True,
            "decision_time": 0,
            "last_action": None,
            "player_id": "2507f1f77bcf86cd799439011",
            "insured": None,
            # "self": True
        },
        3: {
            "cards": [],
            "making_decision": False,
            "player_turn": False,
            "score": "0",
            "user_name": "test_user",
            "current_player": True,
            "decision_time": 0,
            "last_action": None,
            "player_id": "2507f1f77bcf86cd799439011",
            "insured": None,
            # "self": True
        },
    }
    assert on_connect_data["chips"] == {
        1: [
            {"type": "bet", "bet_list": [10], "total_bet": 10.0},
            {"type": "bet_21_3", "bet_list": [], "total_bet": 0},
            {"type": "bet_perfect_pair", "bet_list": [], "total_bet": 0},
        ],
        3: [
            {"type": "bet", "bet_list": [10], "total_bet": 10.0},
            {"type": "bet_21_3", "bet_list": [], "total_bet": 0},
            {"type": "bet_perfect_pair", "bet_list": [], "total_bet": 0},
        ],
    }


@pytest.mark.asyncio
async def test_change_players_sio_and_user_token_on_connect(betting_manager):
    """
    GIVEN: we have an user that can connect and bet to the game
    WHEN: user connects and places bets on two separate boxes and reconnects
    THEN: players before reconnect and after, should have different sid and user_token
    """
    await betting_manager.charge_user(10, 3)
    game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.game_id == TEST_GAME_ID
    )

    assert game_player.user_token == "test_token"
    assert game_player.sid == "test_sid"
    connect_manager = ConnectManager(
        game_id=TEST_GAME_ID, user_token="test_token_2", sid="test_sid_2"
    )
    await connect_manager.connect_to_game()
    game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.game_id == TEST_GAME_ID
    )
    assert game_player.user_token == "test_token_2"
    assert game_player.sid == "test_sid_2"


@pytest.mark.asyncio
async def test_getting_on_connect_deposit_from_cache(betting_manager):
    """
    GIVEN: er have an user that can connect and bet to the game
    WHEN: user connects and places bets on two separate boxes and reconnects
    THEN: on connect should contain deposit of user taken from redis not from core
    """

    await betting_manager.charge_user(10, 3)
    await GamePlayer.find_one(GamePlayer.game_id == TEST_GAME_ID)

    connect_manager = ConnectManager(
        game_id=TEST_GAME_ID, user_token="test_token_2", sid="test_sid_2"
    )
    reconnect_data, _ = await connect_manager.connect_to_game()
    assert reconnect_data["user_deposit"] == TEST_DEPOSIT - 10


@pytest.mark.asyncio
async def test_dealer_connect():
    jwt_token = jwt.encode({}, settings.SECRET_KEY)
    dealer_connect_manager = DealerConnectManager(
        TEST_GAME_ID, "test_sid", str(jwt_token)
    )
    data, sid = await dealer_connect_manager.connect_to_game()
    cache_data = await redis_cache.redis_cache.hgetall(dealer_connect_manager.sid)

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
    assert data["stream_authorization"] == await generate_token_for_stream(
        cache_data["game_id"]
    )
