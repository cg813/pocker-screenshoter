import pytest

from apps.game.documents import GamePlayer, GameRound
from apps.game.services.payment_manager import PaymentManager
from apps.config import settings
from tests.helpers import TEST_GAME_ID


@pytest.mark.asyncio
async def test_evaluate_game_player_suited_trips(betting_manager):
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet")
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet_21_3")
    game_player = await GamePlayer.get_motor_collection().find_one_and_update(
        {"game_id": TEST_GAME_ID},
        {"$set": {"cards": ["1AC", "2AC"]}},
        return_document=True,
    )
    game_round = await GameRound.find_one(GameRound.game_id == TEST_GAME_ID)
    game_round.dealer_cards = ["3AC"]

    await PaymentManager.evaluate_bet_21_3(game_player, game_round)
    game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.game_id == TEST_GAME_ID
    )
    assert game_player.bet_21_3_winning == game_player.bet_21_3 * settings.ST_MULTIPLIER
    assert game_player.bet_21_3_combination == "SUITED TRIPS"


@pytest.mark.asyncio
async def test_evaluate_game_player_straight_flush(betting_manager):
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet")
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet_21_3")
    game_player = await GamePlayer.get_motor_collection().find_one_and_update(
        {"game_id": TEST_GAME_ID},
        {"$set": {"cards": ["1AC", "2KC"]}},
        return_document=True,
    )
    game_round = await GameRound.find_one(GameRound.game_id == TEST_GAME_ID)
    game_round.dealer_cards = ["3QC"]

    await PaymentManager.evaluate_bet_21_3(game_player, game_round)
    game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.game_id == TEST_GAME_ID
    )
    assert game_player.bet_21_3_winning == game_player.bet_21_3 * settings.SF_MULTIPLIER
    assert game_player.bet_21_3_combination == "STRAIGHT FLUSH"


@pytest.mark.asyncio
async def test_evaluate_game_player_low_straight_flush(betting_manager):
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet")
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet_21_3")
    game_player = await GamePlayer.get_motor_collection().find_one_and_update(
        {"game_id": TEST_GAME_ID},
        {"$set": {"cards": ["1AC", "22C"]}},
        return_document=True,
    )
    game_round = await GameRound.find_one(GameRound.game_id == TEST_GAME_ID)
    game_round.dealer_cards = ["33C"]

    await PaymentManager.evaluate_bet_21_3(game_player, game_round)
    game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.game_id == TEST_GAME_ID
    )
    assert game_player.bet_21_3_winning == game_player.bet_21_3 * settings.SF_MULTIPLIER
    assert game_player.bet_21_3_combination == "STRAIGHT FLUSH"


@pytest.mark.asyncio
async def test_evaluate_game_player_three_of_a_kind(betting_manager):
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet")
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet_21_3")
    game_player = await GamePlayer.get_motor_collection().find_one_and_update(
        {"game_id": TEST_GAME_ID},
        {"$set": {"cards": ["1AD", "2AC"]}},
        return_document=True,
    )
    game_round = await GameRound.find_one(GameRound.game_id == TEST_GAME_ID)
    game_round.dealer_cards = ["3AS"]

    await PaymentManager.evaluate_bet_21_3(game_player, game_round)
    game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.game_id == TEST_GAME_ID
    )
    assert game_player.bet_21_3_winning == game_player.bet_21_3 * settings.TK_MULTIPLIER
    assert game_player.bet_21_3_combination == "THREE OF A KIND"


@pytest.mark.asyncio
async def test_evaluate_game_player_straight(betting_manager):
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet")
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet_21_3")
    game_player = await GamePlayer.get_motor_collection().find_one_and_update(
        {"game_id": TEST_GAME_ID},
        {"$set": {"cards": ["1AD", "2KC"]}},
        return_document=True,
    )
    game_round = await GameRound.find_one(GameRound.game_id == TEST_GAME_ID)
    game_round.dealer_cards = ["3QS"]

    await PaymentManager.evaluate_bet_21_3(game_player, game_round)
    game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.game_id == TEST_GAME_ID
    )
    assert game_player.bet_21_3_winning == game_player.bet_21_3 * settings.S_MULTIPLIER
    assert game_player.bet_21_3_combination == "STRAIGHT"


@pytest.mark.asyncio
async def test_evaluate_game_player_low_straight(betting_manager):
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet")
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet_21_3")
    game_player = await GamePlayer.get_motor_collection().find_one_and_update(
        {"game_id": TEST_GAME_ID},
        {"$set": {"cards": ["1AD", "22C"]}},
        return_document=True,
    )
    game_round = await GameRound.find_one(GameRound.game_id == TEST_GAME_ID)
    game_round.dealer_cards = ["33S"]

    await PaymentManager.evaluate_bet_21_3(game_player, game_round)
    game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.game_id == TEST_GAME_ID
    )
    assert game_player.bet_21_3_winning == game_player.bet_21_3 * settings.S_MULTIPLIER
    assert game_player.bet_21_3_combination == "STRAIGHT"


@pytest.mark.asyncio
async def test_evaluate_game_player_flush(betting_manager):
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet")
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet_21_3")
    game_player = await GamePlayer.get_motor_collection().find_one_and_update(
        {"game_id": TEST_GAME_ID},
        {"$set": {"cards": ["12D", "2KD"]}},
        return_document=True,
    )
    game_round = await GameRound.find_one(GameRound.game_id == TEST_GAME_ID)
    game_round.dealer_cards = ["3QD"]

    await PaymentManager.evaluate_bet_21_3(game_player, game_round)
    game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.game_id == TEST_GAME_ID
    )
    assert game_player.bet_21_3_winning == game_player.bet_21_3 * settings.F_MULTIPLIER
    assert game_player.bet_21_3_combination == "FLUSH"


@pytest.mark.asyncio
async def test_evaluate_game_player_with_no_21_3_combination(betting_manager):
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet")
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet_21_3")
    game_player = await GamePlayer.get_motor_collection().find_one_and_update(
        {"game_id": TEST_GAME_ID},
        {"$set": {"cards": ["12S", "2KC"]}},
        return_document=True,
    )
    game_round = await GameRound.find_one(GameRound.game_id == TEST_GAME_ID)
    game_round.dealer_cards = ["3QS"]

    await PaymentManager.evaluate_bet_21_3(game_player, game_round)
    game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.game_id == TEST_GAME_ID
    )
    assert game_player.bet_21_3_winning == 0
    assert game_player.bet_21_3_combination is None
