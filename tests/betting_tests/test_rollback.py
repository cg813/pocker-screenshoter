import pytest

from apps.game.documents import GamePlayer, GameRound
from apps.game.services.custom_exception import ValidationError
from apps.connections import redis_cache
from tests.helpers import TEST_DEPOSIT, TEST_ROUND_ID


@pytest.mark.asyncio
async def test_make_rollback(betting_and_rollback_manager):
    """ """
    betting_manager, rollback_manager = betting_and_rollback_manager

    bet_data = await betting_manager.charge_user(amount=30, seat_number=1)
    game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.sid == rollback_manager.sid, GamePlayer.seat_number == 1
    )
    assert game_player.bet == bet_data.get("total_bet")
    assert game_player.deposit == bet_data.get("user_deposit")

    rollback_data = await rollback_manager.make_rollback(seat_number=1)
    updated_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.sid == rollback_manager.sid, GamePlayer.seat_number == 1
    )
    assert rollback_data["seat_number"] == 1
    assert updated_game_player.bet == 0
    assert updated_game_player.deposit == bet_data.get("user_deposit") + 30
    assert len(updated_game_player.bet_list) == 0


@pytest.mark.asyncio
async def test_make_rollback_when_bet_list_is_empty(betting_and_rollback_manager):
    betting_manager, rollback_manager = betting_and_rollback_manager

    bet_data = await betting_manager.charge_user(amount=30, seat_number=1)

    game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.sid == rollback_manager.sid, GamePlayer.seat_number == 1
    )
    assert game_player.bet == bet_data.get("total_bet")
    assert game_player.deposit == bet_data.get("user_deposit")

    rollback_data = await rollback_manager.make_rollback(seat_number=1)
    updated_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.sid == rollback_manager.sid, GamePlayer.seat_number == 1
    )
    assert rollback_data["seat_number"] == 1
    assert updated_game_player.bet == 0
    assert updated_game_player.deposit == bet_data.get("user_deposit") + 30
    assert len(updated_game_player.bet_list) == 0

    with pytest.raises(ValidationError) as error:
        await rollback_manager.make_rollback(seat_number=1)
        assert str(error) == "There is no bet to rollback"


@pytest.mark.asyncio
async def test_make_rollback_on_different_seats(betting_and_rollback_manager):
    betting_manager, rollback_manager = betting_and_rollback_manager

    first_bet_data = await betting_manager.charge_user(amount=30, seat_number=1)
    assert first_bet_data.get("total_bet") == 30
    assert first_bet_data.get("bet") == 30
    assert first_bet_data.get("bet_list") == [30]

    second_bet_data = await betting_manager.charge_user(amount=10, seat_number=3)
    assert second_bet_data.get("total_bet") == 10
    assert second_bet_data.get("bet") == 10
    assert second_bet_data.get("bet_list") == [10]

    rollback_data = await rollback_manager.make_rollback(seat_number=1)

    player_seat_1: GamePlayer = await GamePlayer.find_one(
        GamePlayer.sid == rollback_manager.sid, GamePlayer.seat_number == 1
    )
    player_seat_3: GamePlayer = await GamePlayer.find_one(
        GamePlayer.sid == rollback_manager.sid, GamePlayer.seat_number == 3
    )
    assert rollback_data["seat_number"] == 1
    assert player_seat_1.bet == 0
    assert player_seat_1.deposit == second_bet_data.get(
        "user_deposit"
    ) + first_bet_data.get("bet")
    assert player_seat_3.bet == 10


@pytest.mark.asyncio
async def test_make_rollback_after_betting_time_is_over(betting_and_rollback_manager):
    betting_manager, rollback_manager = betting_and_rollback_manager

    first_bet_data = await betting_manager.charge_user(amount=30, seat_number=1)
    assert first_bet_data.get("total_bet") == 30
    assert first_bet_data.get("bet") == 30
    assert first_bet_data.get("bet_list") == [30]

    game_round = await GameRound.find_one({})
    game_round.start_timestamp = int(game_round.start_timestamp) - 20
    await game_round.save()

    with pytest.raises(ValidationError) as error:
        await rollback_manager.make_rollback(seat_number=1)
        assert str(error) == "Rollback time is over"


@pytest.mark.asyncio
async def test_action_list_when_making_rollbacks(betting_and_rollback_manager):

    betting_manager, rollback_manager = betting_and_rollback_manager

    await betting_manager.charge_user(amount=30, seat_number=1)
    bet_data_2 = await betting_manager.charge_user(amount=20, seat_number=1)
    await GamePlayer.find_one(
        GamePlayer.sid == rollback_manager.sid, GamePlayer.seat_number == 1
    )
    await rollback_manager.make_rollback(seat_number=1)
    await rollback_manager.make_rollback(seat_number=1)

    updated_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.sid == rollback_manager.sid, GamePlayer.seat_number == 1
    )
    assert updated_game_player.action_list[-1].get("rollback") == 30
    assert updated_game_player.bet == 0
    assert updated_game_player.deposit == bet_data_2.get("user_deposit") + 50
    assert len(updated_game_player.bet_list) == 0


@pytest.mark.asyncio
async def test_action_list_when_making_rollbacks_with_different_seats(
    betting_and_rollback_manager,
):

    betting_manager, rollback_manager = betting_and_rollback_manager

    await betting_manager.charge_user(amount=30, seat_number=1)
    await betting_manager.charge_user(amount=20, seat_number=3)

    rollback_data = await rollback_manager.make_rollback(seat_number=3)

    updated_game_player_1: GamePlayer = await GamePlayer.find_one(
        GamePlayer.sid == rollback_manager.sid, GamePlayer.seat_number == 1
    )
    updated_game_player_3: GamePlayer = await GamePlayer.find_one(
        GamePlayer.sid == rollback_manager.sid, GamePlayer.seat_number == 3
    )
    assert rollback_data["seat_number"] == 3
    assert updated_game_player_1.seat_number == 1
    assert updated_game_player_1.action_list[0].get("bet") == 30
    assert updated_game_player_3.seat_number == 3
    assert updated_game_player_3.action_list[0].get("bet") == 20
    assert updated_game_player_3.action_list[1].get("rollback") == 20


@pytest.mark.asyncio
async def test_rollback_before_placing_bet(betting_and_rollback_manager):
    _, rollback_manager = betting_and_rollback_manager

    with pytest.raises(ValidationError) as error:
        await rollback_manager.make_rollback(seat_number=2)
        assert str(error) == "Player has not placed any bet yet"


@pytest.mark.asyncio
async def test_rollback_before_placing_bet_21_3(betting_and_rollback_manager):
    betting_manager, rollback_manager = betting_and_rollback_manager
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet")
    try:
        await rollback_manager.make_rollback(seat_number=1, rollback_type="bet_21_3")
    except ValidationError as error:
        raised_exception = str(error)

    assert raised_exception == "There is no bet to rollback"


@pytest.mark.asyncio
async def test_rollback_bet_21_3(betting_and_rollback_manager):
    betting_manager, rollback_manager = betting_and_rollback_manager
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet")
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet_21_3")
    rollback_data = await rollback_manager.make_rollback(
        seat_number=1, rollback_type="bet_21_3"
    )
    game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.sid == rollback_manager.sid, GamePlayer.seat_number == 1
    )
    assert game_player.bet_21_3 == 0
    assert game_player.bet_21_3_list == []
    assert game_player.bet == 10
    assert game_player.bet_list == [10]
    assert rollback_data.get("total_bet") == 10
    assert rollback_data.get("balance") == TEST_DEPOSIT - 10
    assert rollback_data.get("rollback_type") == "bet_21_3"
    assert rollback_data.get("bet_list") == []
    assert rollback_data.get("user_total_bet") == 10


@pytest.mark.asyncio
async def test_rollback_before_placing_bet_perfect_pair(betting_and_rollback_manager):
    betting_manager, rollback_manager = betting_and_rollback_manager
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet")
    try:
        await rollback_manager.make_rollback(
            seat_number=1, rollback_type="bet_perfect_pair"
        )
    except ValidationError as error:
        raised_exception = str(error)

    assert raised_exception == "There is no bet to rollback"


@pytest.mark.asyncio
async def test_rollback_bet_perfect_pair(betting_and_rollback_manager):
    betting_manager, rollback_manager = betting_and_rollback_manager
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet")
    await betting_manager.charge_user(
        amount=10, seat_number=1, bet_type="bet_perfect_pair"
    )
    rollback_data = await rollback_manager.make_rollback(
        seat_number=1, rollback_type="bet_perfect_pair"
    )
    game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.sid == rollback_manager.sid, GamePlayer.seat_number == 1
    )
    assert game_player.bet_21_3 == 0
    assert game_player.bet_21_3_list == []
    assert game_player.bet == 10
    assert game_player.bet_list == [10]
    assert rollback_data.get("total_bet") == 10
    assert rollback_data.get("balance") == TEST_DEPOSIT - 10
    assert rollback_data.get("rollback_type") == "bet_perfect_pair"
    assert rollback_data.get("bet_list") == []
    assert rollback_data.get("user_total_bet") == 10


@pytest.mark.asyncio
async def test_make_rollback_with_unknown_rollback_type(betting_and_rollback_manager):
    betting_manager, rollback_manager = betting_and_rollback_manager
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet")
    try:
        await rollback_manager.make_rollback(seat_number=1, rollback_type="unknown")
    except ValidationError as error:
        raised_exception = str(error)

    assert raised_exception == "Rollback type is unknown"


@pytest.mark.asyncio
async def test_undo_main_bet_and_side_bet_21_3_more_than_main_bet(
    betting_and_rollback_manager,
):
    betting_manager, rollback_manager = betting_and_rollback_manager
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet")
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet")
    await betting_manager.charge_user(amount=20, seat_number=1, bet_type="bet_21_3")
    try:
        await rollback_manager.make_rollback(seat_number=1, rollback_type="bet")
    except ValidationError as error:
        raised_error = str(error)

    assert raised_error == "Side bet 21+3 can not be more than main bet"


@pytest.mark.asyncio
async def test_undo_main_bet_and_side_bet_perfect_pair_more_than_main_bet(
    betting_and_rollback_manager,
):
    betting_manager, rollback_manager = betting_and_rollback_manager
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet")
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet")
    await betting_manager.charge_user(
        amount=20, seat_number=1, bet_type="bet_perfect_pair"
    )
    try:
        await rollback_manager.make_rollback(seat_number=1, rollback_type="bet")
    except ValidationError as error:
        raised_error = str(error)

    assert raised_error == "Side bet Perfect Pair can not be more than main bet"


@pytest.mark.asyncio
async def test_no_bet_seat_after_rollback(betting_and_rollback_manager):
    betting_manager, rollback_manager = betting_and_rollback_manager
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet")
    await rollback_manager.make_rollback(seat_number=1, rollback_type="bet")
    data = await redis_cache.get(f"{TEST_ROUND_ID}:1")
    assert data is None
