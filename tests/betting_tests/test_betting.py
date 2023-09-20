import pytest

from apps.config import settings
from apps.connections import redis_cache
from apps.game.documents import GamePlayer, GameRound
from apps.game.betting.betting_manager import BettingManager
from apps.game.services.connect_manager import ConnectManager
from apps.game.services.custom_exception import ValidationError
from tests.helpers import TEST_DEPOSIT, TEST_GAME_ID, mock_check_if_user_can_connect


@pytest.mark.asyncio
async def test_place_bet(betting_manager):
    """ """
    data = await betting_manager.charge_user(amount=10, seat_number=1)
    game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.game_id == TEST_GAME_ID
    )
    assert game_player.bet == 10
    assert game_player.bet_list[0] == 10
    assert game_player.seat_number == 1
    assert len(game_player.bet_list) == 1
    assert game_player.deposit == TEST_DEPOSIT - 10
    assert data == {
        "bet_type": "bet",
        "seat_number": 1,
        "total_bet": 10,
        "bet": 10,
        "player_id": game_player.user_id + game_player.merchant,
        "user_deposit": TEST_DEPOSIT - 10,
        "bet_list": [10],
        "user_total_bet": 10,
    }


@pytest.mark.asyncio
async def test_place_multiple_bets(betting_manager):
    bet_response = await betting_manager.charge_user(10, 1)
    second_bet_response = await betting_manager.charge_user(10, 1)
    game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.game_id == TEST_GAME_ID
    )
    assert game_player.bet == 20
    assert game_player.bet_list[0] == 10
    assert game_player.bet_list[1] == 10
    assert game_player.seat_number == 1
    assert len(game_player.bet_list) == 2
    assert game_player.deposit == TEST_DEPOSIT - 20
    assert bet_response == {
        "bet_type": "bet",
        "seat_number": 1,
        "total_bet": 10,
        "bet": 10,
        "player_id": game_player.user_id + game_player.merchant,
        "user_deposit": TEST_DEPOSIT - 10,
        "bet_list": [10],
        "user_total_bet": 10,
    }
    assert second_bet_response == {
        "bet_type": "bet",
        "seat_number": 1,
        "total_bet": 20,
        "bet": 20,
        "player_id": game_player.user_id + game_player.merchant,
        "user_deposit": TEST_DEPOSIT - 20,
        "bet_list": [10, 10],
        "user_total_bet": 20,
    }


@pytest.mark.asyncio
async def test_place_bet_more_than_allowed(betting_manager):
    with pytest.raises(ValidationError) as error:
        await betting_manager.charge_user(300, 3)
        assert str(error) == "placing more than maximum bet is not allowed"


@pytest.mark.asyncio
async def test_place_bet_less_than_allowed(betting_manager):
    with pytest.raises(ValidationError) as error:
        await betting_manager.charge_user(2, 3)
        assert str(error) == "placing less than minimum bet is not allowed"


@pytest.mark.asyncio
async def test_place_bets_on_multiple_seats(betting_manager):
    await betting_manager.charge_user(10, 1)
    await betting_manager.charge_user(20, 5)
    game_players = await GamePlayer.find(GamePlayer.game_id == TEST_GAME_ID).to_list()
    assert len(game_players) == 2
    assert game_players[0].bet == 10
    assert game_players[0].seat_number == 1
    assert game_players[0].deposit == TEST_DEPOSIT - 10
    assert game_players[0].bet_list[0] == 10
    assert game_players[1].bet == 20
    assert game_players[1].bet_list[0] == 20
    assert game_players[1].deposit == TEST_DEPOSIT - 30


@pytest.mark.asyncio
async def test_place_bet_when_seat_is_taken(betting_manager, monkeypatch):
    await betting_manager.charge_user(10, 1)
    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )
    connect_manager = ConnectManager(TEST_GAME_ID, "test_token_2", "test_sid_2")
    await connect_manager.connect_to_game()

    user_session_data = await redis_cache.redis_cache.hgetall("test_sid_2")
    betting_manager = BettingManager(user_session_data, "test_sid_2", "bet")
    await betting_manager.charge_user(10, 1)
    game_players = await GamePlayer.find(GamePlayer.game_id == TEST_GAME_ID).to_list()
    assert len(game_players) == 1


@pytest.mark.asyncio
async def test_place_bets_after_betting_time_is_over(betting_manager):
    game_round: GameRound = await GameRound.find_one(GameRound.game_id == TEST_GAME_ID)
    game_round.start_timestamp = int(game_round.start_timestamp) - 20
    await game_round.save()
    with pytest.raises(ValidationError) as error:
        await betting_manager.charge_user(10, 5)
        assert str(error) == "betting time is over"
        game_player = await GamePlayer.find_one(GamePlayer.seat_number == 5)
        assert game_player is None


@pytest.mark.asyncio
async def test_betting_on_seat_out_of_range(betting_manager):
    """
    GIVEN: we have and user that can connect and bet to the game
    WHEN: user connects and tries to bet on 8th (non-existing) seat
    THEN: error event should be sent to the user saying: "seat number out of range"
    """
    with pytest.raises(ValidationError) as error:
        await betting_manager.charge_user(10, 10)
        assert str(error) == "seat number out of range"


@pytest.mark.asyncio
async def test_action_list_when_placing_bets(betting_manager):

    await betting_manager.charge_user(amount=10, seat_number=1)
    await betting_manager.charge_user(amount=20, seat_number=1)
    game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.game_id == TEST_GAME_ID
    )
    assert game_player.action_list[0].get("bet") == 10
    assert game_player.action_list[1].get("bet") == 20
    assert game_player.bet == 30
    assert game_player.seat_number == 1


@pytest.mark.asyncio
async def test_action_list_when_placing_bets_with_different_seats(betting_manager):

    await betting_manager.charge_user(amount=10, seat_number=1)
    await betting_manager.charge_user(amount=20, seat_number=3)
    game_player_1: GamePlayer = await GamePlayer.find_one(
        GamePlayer.game_id == TEST_GAME_ID, GamePlayer.seat_number == 1
    )
    game_player_2: GamePlayer = await GamePlayer.find_one(
        GamePlayer.game_id == TEST_GAME_ID, GamePlayer.seat_number == 3
    )

    assert game_player_1.seat_number == 1
    assert game_player_1.action_list[0].get("bet") == 10
    assert game_player_2.seat_number == 3
    assert game_player_2.action_list[0].get("bet") == 20


@pytest.mark.asyncio
async def test_place_side_bet_21_3_before_placing_main_bet(betting_manager):
    with pytest.raises(ValidationError) as error:
        await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet_21_3")
        assert str(error) == "Can not place side bet before placing main bet."


@pytest.mark.asyncio
async def test_place_side_bet_21_3_before_placing_main_bet(betting_manager):
    with pytest.raises(ValidationError) as error:
        await betting_manager.charge_user(amount=-10, seat_number=1, bet_type="bet")
        assert str(error) == "Unsupported amount"


@pytest.mark.asyncio
async def test_placing_side_bet_21_3_more_than_main_bet(betting_manager):
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet")
    with pytest.raises(ValidationError) as error:
        await betting_manager.charge_user(amount=20, seat_number=1, bet_type="bet_21_3")
        assert str(error) == "Side bet can not be more than main bet"


@pytest.mark.asyncio
async def test_place_side_bet_21_3_more_than_allowed(betting_manager):
    await betting_manager.charge_user(
        amount=settings.MAX_SIDE_BET + 5, seat_number=1, bet_type="bet"
    )
    with pytest.raises(ValidationError) as error:
        await betting_manager.charge_user(
            amount=settings.MAX_SIDE_BET + 5, seat_number=1, bet_type="bet_21_3"
        )
        assert str(error) == "Placing more than maximum side bet limit is not allowed"


@pytest.mark.asyncio
async def test_place_maximum_side_bet_21_3(betting_manager):
    await betting_manager.charge_user(
        amount=settings.MAX_SIDE_BET, seat_number=1, bet_type="bet"
    )
    await betting_manager.charge_user(
        amount=settings.MAX_SIDE_BET, seat_number=1, bet_type="bet_21_3"
    )
    game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.game_id == TEST_GAME_ID
    )
    assert game_player.bet_21_3 == settings.MAX_SIDE_BET


@pytest.mark.asyncio
async def test_place_side_bet_21_3_after_placing_main_bet(betting_manager):
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet")
    data = await betting_manager.charge_user(
        amount=10, seat_number=1, bet_type="bet_21_3"
    )
    game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.game_id == TEST_GAME_ID
    )
    assert game_player.bet == 10
    assert game_player.bet_list[0] == 10
    assert game_player.bet_21_3 == 10
    assert game_player.bet_21_3_list[0] == 10
    assert game_player.seat_number == 1
    assert len(game_player.bet_list) == 1
    assert len(game_player.bet_21_3_list) == 1
    assert game_player.deposit == TEST_DEPOSIT - 20
    assert data == {
        "bet_type": "bet_21_3",
        "seat_number": 1,
        "total_bet": 20,
        "bet_21_3": 10,
        "bet_21_3_list": [10],
        "player_id": game_player.user_id + game_player.merchant,
        "user_deposit": TEST_DEPOSIT - 20,
        "user_total_bet": 20,
    }


@pytest.mark.asyncio
async def test_place_side_bet_perfect_pair_before_placing_main_bet(betting_manager):
    with pytest.raises(ValidationError) as error:
        await betting_manager.charge_user(
            amount=10, seat_number=1, bet_type="bet_perfect_pair"
        )
        assert str(error) == "Can not place side bet before placing main bet."


@pytest.mark.asyncio
async def test_place_side_bet_perfect_pair_more_than_allowed(betting_manager):
    await betting_manager.charge_user(
        amount=settings.MAX_SIDE_BET + 5, seat_number=1, bet_type="bet"
    )
    with pytest.raises(ValidationError) as error:
        await betting_manager.charge_user(
            amount=settings.MAX_SIDE_BET + 5, seat_number=1, bet_type="bet_perfect_pair"
        )
        assert str(error) == "Placing more than side maximum bet limit is not allowed"


@pytest.mark.asyncio
async def test_place_maximum_side_bet_perfect_pair(betting_manager):
    await betting_manager.charge_user(
        amount=settings.MAX_SIDE_BET, seat_number=1, bet_type="bet"
    )
    await betting_manager.charge_user(
        amount=settings.MAX_SIDE_BET, seat_number=1, bet_type="bet_perfect_pair"
    )
    game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.game_id == TEST_GAME_ID
    )
    assert game_player.bet_perfect_pair == settings.MAX_SIDE_BET


@pytest.mark.asyncio
async def test_placing_side_bet_perfect_pair_more_than_main_bet(betting_manager):
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet")
    with pytest.raises(ValidationError) as error:
        await betting_manager.charge_user(
            amount=20, seat_number=1, bet_type="bet_perfect_pair"
        )
        assert str(error) == "Side bet can not be more than main bet"


@pytest.mark.asyncio
async def test_place_side_bet_perfect_pair_after_placing_main_bet(betting_manager):
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet")
    data = await betting_manager.charge_user(
        amount=10, seat_number=1, bet_type="bet_perfect_pair"
    )
    game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.game_id == TEST_GAME_ID
    )
    assert game_player.bet == 10
    assert game_player.bet_list[0] == 10
    assert game_player.bet_perfect_pair == 10
    assert game_player.bet_perfect_pair_list[0] == 10
    assert game_player.seat_number == 1
    assert len(game_player.bet_list) == 1
    assert len(game_player.bet_perfect_pair_list) == 1
    assert game_player.deposit == TEST_DEPOSIT - 20
    assert data == {
        "bet_type": "bet_perfect_pair",
        "seat_number": 1,
        "total_bet": 20,
        "bet_perfect_pair": 10,
        "bet_perfect_pair_list": [10],
        "player_id": game_player.user_id + game_player.merchant,
        "user_deposit": TEST_DEPOSIT - 20,
        "user_total_bet": 20,
    }


@pytest.mark.asyncio
async def test_make_bet_with_unknown_bet_type(betting_manager):
    with pytest.raises(ValidationError) as error:
        await betting_manager.charge_user(amount=10, seat_number=1, bet_type="unknown")
        assert str(error) == "Bet type is unknown"
