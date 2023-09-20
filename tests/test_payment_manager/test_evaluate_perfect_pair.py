import pytest

from apps.game.documents import GamePlayer
from apps.game.services.payment_manager import PaymentManager
from apps.config import settings
from tests.helpers import TEST_GAME_ID


@pytest.mark.asyncio
async def test_evaluate_game_player_perfect_pair(betting_manager):
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet")
    await betting_manager.charge_user(
        amount=10, seat_number=1, bet_type="bet_perfect_pair"
    )
    game_player = await GamePlayer.get_motor_collection().find_one_and_update(
        {"game_id": TEST_GAME_ID},
        {"$set": {"cards": ["1AC", "2AC"]}},
        return_document=True,
    )
    await PaymentManager.evaluate_bet_perfect_pair(game_player)
    game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.game_id == TEST_GAME_ID
    )

    assert (
        game_player.bet_perfect_pair_winning
        == game_player.bet_perfect_pair * settings.PP_MULTIPLIER
    )
    assert game_player.bet_perfect_pair_combination == "PERFECT PAIR"


@pytest.mark.asyncio
async def test_evaluate_game_player_colored_pair(betting_manager):
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet")
    await betting_manager.charge_user(
        amount=10, seat_number=1, bet_type="bet_perfect_pair"
    )
    game_player = await GamePlayer.get_motor_collection().find_one_and_update(
        {"game_id": TEST_GAME_ID},
        {"$set": {"cards": ["1AC", "2AS"]}},
        return_document=True,
    )
    await PaymentManager.evaluate_bet_perfect_pair(game_player)
    game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.game_id == TEST_GAME_ID
    )

    assert (
        game_player.bet_perfect_pair_winning
        == game_player.bet_perfect_pair * settings.CP_MULTIPLIER
    )
    assert game_player.bet_perfect_pair_combination == "COLORED PAIR"


@pytest.mark.asyncio
async def test_evaluate_game_player_mixed_pair(betting_manager):
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet")
    await betting_manager.charge_user(
        amount=10, seat_number=1, bet_type="bet_perfect_pair"
    )
    game_player = await GamePlayer.get_motor_collection().find_one_and_update(
        {"game_id": TEST_GAME_ID},
        {"$set": {"cards": ["1AC", "2AD"]}},
        return_document=True,
    )
    await PaymentManager.evaluate_bet_perfect_pair(game_player)
    game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.game_id == TEST_GAME_ID
    )
    assert (
        game_player.bet_perfect_pair_winning
        == game_player.bet_perfect_pair * settings.MP_MULTIPLIER
    )
    assert game_player.bet_perfect_pair_combination == "MIXED PAIR"


@pytest.mark.asyncio
async def test_evaluate_perfect_pair_without_any_winning(betting_manager):
    await betting_manager.charge_user(amount=10, seat_number=1, bet_type="bet")
    await betting_manager.charge_user(
        amount=10, seat_number=1, bet_type="bet_perfect_pair"
    )
    game_player = await GamePlayer.get_motor_collection().find_one_and_update(
        {"game_id": TEST_GAME_ID},
        {"$set": {"cards": ["12C", "2AD"]}},
        return_document=True,
    )
    await PaymentManager.evaluate_bet_perfect_pair(game_player)
    game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.game_id == TEST_GAME_ID
    )

    assert game_player.bet_perfect_pair_winning == 0
    assert game_player.bet_perfect_pair_combination is None
