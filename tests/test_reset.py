from apps.game.documents import GameRound
import pytest

from apps.game.services.payment_manager import ResetManager
from apps.game.services.custom_exception import ValidationError
from .helpers import TEST_GAME_ID


@pytest.mark.asyncio
async def test_make_reset_when_betting_time_is_not_over(betting_manager):
    await betting_manager.charge_user(amount=20, seat_number=1)
    game_round = await GameRound.find_one({})
    reset_manager = ResetManager(TEST_GAME_ID, game_round)
    with pytest.raises(ValidationError) as error:
        await reset_manager.reset()
        assert str(error) == "Can not reset the game before betting time is over"


@pytest.mark.asyncio
async def test_duplicate_reset(betting_manager):
    await betting_manager.charge_user(amount=20, seat_number=1)
    game_round = await GameRound.find_one({})
    game_round.start_timestamp = None
    reset_manager = ResetManager(TEST_GAME_ID, game_round)
    with pytest.raises(ValidationError) as error:
        await reset_manager.reset()
        assert error == "Game is reset already"
