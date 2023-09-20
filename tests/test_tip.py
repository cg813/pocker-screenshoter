import pytest

from apps.game.documents import Tip
from tests.helpers import TEST_SESSION_DATA
from apps.game.services.custom_exception import ValidationError


@pytest.mark.asyncio
async def test_tip_dealer(betting_manager):
    data = await betting_manager.tip_dealer(10, TEST_SESSION_DATA)
    tip = await Tip.find_one({})

    assert f"{tip.user_id}{tip.merchant_id}" == data["player_id"]
    assert tip.amount == 10


@pytest.mark.asyncio
async def test_tip_dealer_negative_amount(betting_manager):
    with pytest.raises(ValidationError) as error:
        await betting_manager.tip_dealer(-10, TEST_SESSION_DATA)
        assert str(error) == "Unsupported amount"
