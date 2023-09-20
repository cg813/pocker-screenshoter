import pytest

from apps.connections import redis_cache
from apps.game.cards.actions_card_manager import ActionCardManager
from apps.game.documents import GamePlayer, GameRound
from apps.game.cards.cards_manager import EuropeanCardsManager
from apps.game.services.custom_exception import ValidationError
from tests.helpers import (
    TEST_ROUND_ID,
    get_round_and_finish_betting_time,
    scan_multiple_cards,
)


@pytest.mark.asyncio
async def test_card_scan(betting_manager):
    await betting_manager.charge_user(10, 1)
    await betting_manager.charge_user(10, 3)
    await get_round_and_finish_betting_time()
    user_session_data = await redis_cache.redis_cache.hgetall("test_sid")
    card_manager = EuropeanCardsManager(user_session_data, TEST_ROUND_ID)
    await scan_multiple_cards(["12C", "14C", "1JS", "1QD", "1KD"], card_manager)
    game_player: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    second_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.seat_number == 3
    )
    game_round: GameRound = await GameRound.find_one({})
    assert game_round.dealer_cards == ["1JS"]
    assert game_player.cards == ["12C", "1QD"]
    assert second_game_player.cards == ["14C", "1KD"]
    assert game_round.finished_dealing is True
    assert game_player.making_decision is True
    assert game_player.decision_time is not None


@pytest.mark.asyncio
async def test_dealing_cards_one_seat(betting_manager):
    await betting_manager.charge_user(10, 1)
    await get_round_and_finish_betting_time()
    user_session_data = await redis_cache.redis_cache.hgetall("test_sid")
    card_manager = EuropeanCardsManager(user_session_data, TEST_ROUND_ID)
    await scan_multiple_cards(["12C", "1JS", "19S"], card_manager)
    game_player: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    game_round: GameRound = await GameRound.find_one({})
    assert game_player.cards == ["12C", "19S"]
    assert game_round.dealer_cards == ["1JS"]
    assert game_round.finished_dealing is True
    assert game_player.making_decision is True
    assert game_player.decision_time is not None


@pytest.mark.asyncio
async def test_dealing_card_on_two_seats(betting_manager):
    await betting_manager.charge_user(20, 1)
    await betting_manager.charge_user(10, 3)
    await get_round_and_finish_betting_time()
    user_session_data = await redis_cache.redis_cache.hgetall("test_sid")
    card_manager = EuropeanCardsManager(user_session_data, TEST_ROUND_ID)
    await scan_multiple_cards(["12C", "19S", "1JD", "1QS", "1AS"], card_manager)
    game_player: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    second_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.seat_number == 3
    )
    game_round: GameRound = await GameRound.find_one({})
    assert game_player.cards == ["12C", "1QS"]
    assert second_game_player.cards == ["19S", "1AS"]
    assert game_round.dealer_cards == ["1JD"]
    assert game_round.finished_dealing is True
    assert game_player.making_decision is True
    assert game_player.decision_time is not None


@pytest.mark.asyncio
async def test_dealing_card_on_three_seats(betting_manager):
    await betting_manager.charge_user(30, 1)
    await betting_manager.charge_user(15, 3)
    await betting_manager.charge_user(15, 5)
    await get_round_and_finish_betting_time()
    user_session_data = await redis_cache.redis_cache.hgetall("test_sid")
    card_manager = EuropeanCardsManager(user_session_data, TEST_ROUND_ID)
    await scan_multiple_cards(
        ["12C", "19S", "1JD", "1QS", "1AS", "13S", "1TS"], card_manager
    )
    game_player: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    second_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.seat_number == 3
    )
    third_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.seat_number == 5
    )
    game_round: GameRound = await GameRound.find_one({})
    assert game_player.cards == ["12C", "1AS"]
    assert second_game_player.cards == ["19S", "13S"]
    assert third_game_player.cards == ["1JD", "1TS"]
    assert game_round.dealer_cards == ["1QS"]
    assert game_round.finished_dealing is True
    assert game_player.making_decision is True
    assert game_player.decision_time is not None


@pytest.mark.asyncio
async def test_dealing_card_on_four_seats(betting_manager):
    await betting_manager.charge_user(30, 1)
    await betting_manager.charge_user(15, 3)
    await betting_manager.charge_user(15, 5)
    await betting_manager.charge_user(25, 7)
    await get_round_and_finish_betting_time()
    user_session_data = await redis_cache.redis_cache.hgetall("test_sid")
    card_manager = EuropeanCardsManager(user_session_data, TEST_ROUND_ID)
    await scan_multiple_cards(
        ["12C", "19S", "1JD", "1QS", "12S", "13S", "1TS", "12D", "13D"], card_manager
    )
    game_player: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    second_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.seat_number == 3
    )
    third_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.seat_number == 5
    )
    fourth_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.seat_number == 7
    )
    game_round: GameRound = await GameRound.find_one({})
    assert game_player.cards == ["12C", "13S"]
    assert second_game_player.cards == ["19S", "1TS"]
    assert third_game_player.cards == ["1JD", "12D"]
    assert fourth_game_player.cards == ["1QS", "13D"]
    assert game_round.dealer_cards == ["12S"]
    assert game_round.finished_dealing is True
    assert game_player.making_decision is True
    assert game_player.decision_time is not None


@pytest.mark.asyncio
async def test_dealing_card_on_five_seats(betting_manager):
    await betting_manager.charge_user(30, 1)
    await betting_manager.charge_user(15, 3)
    await betting_manager.charge_user(15, 5)
    await betting_manager.charge_user(25, 7)
    await betting_manager.charge_user(10, 9)
    await get_round_and_finish_betting_time()
    user_session_data = await redis_cache.redis_cache.hgetall("test_sid")
    card_manager = EuropeanCardsManager(user_session_data, TEST_ROUND_ID)
    await scan_multiple_cards(
        ["12C", "19S", "1JD", "1QS", "1AS", "13S", "1TS", "12D", "13D", "19C", "18H"],
        card_manager,
    )
    game_player: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    second_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.seat_number == 3
    )
    third_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.seat_number == 5
    )
    fourth_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.seat_number == 7
    )
    fifth_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.seat_number == 9
    )
    game_round: GameRound = await GameRound.find_one({})
    assert game_player.cards == ["12C", "1TS"]
    assert second_game_player.cards == ["19S", "12D"]
    assert third_game_player.cards == ["1JD", "13D"]
    assert fourth_game_player.cards == ["1QS", "19C"]
    assert fifth_game_player.cards == ["1AS", "18H"]
    assert game_round.dealer_cards == ["13S"]
    assert game_round.finished_dealing is True
    assert game_player.making_decision is True
    assert game_player.decision_time is not None


@pytest.mark.asyncio
async def test_dealing_card_on_six_seats(betting_manager):
    await betting_manager.charge_user(30, 1)
    await betting_manager.charge_user(15, 3)
    await betting_manager.charge_user(15, 5)
    await betting_manager.charge_user(25, 7)
    await betting_manager.charge_user(10, 9)
    await betting_manager.charge_user(10, 11)
    await get_round_and_finish_betting_time()
    user_session_data = await redis_cache.redis_cache.hgetall("test_sid")
    card_manager = EuropeanCardsManager(user_session_data, TEST_ROUND_ID)
    await scan_multiple_cards(
        [
            "12C",
            "19S",
            "1JD",
            "1QS",
            "1AS",
            "13S",
            "1TS",
            "12D",
            "13D",
            "19C",
            "18H",
            "17S",
            "17H",
        ],
        card_manager,
    )
    game_player: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    second_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.seat_number == 3
    )
    third_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.seat_number == 5
    )
    fourth_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.seat_number == 7
    )
    fifth_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.seat_number == 9
    )
    sixth_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.seat_number == 11
    )
    game_round: GameRound = await GameRound.find_one({})
    assert game_player.cards == ["12C", "12D"]
    assert second_game_player.cards == ["19S", "13D"]
    assert third_game_player.cards == ["1JD", "19C"]
    assert fourth_game_player.cards == ["1QS", "18H"]
    assert fifth_game_player.cards == ["1AS", "17S"]
    assert sixth_game_player.cards == ["13S", "17H"]
    assert game_round.dealer_cards == ["1TS"]
    assert game_round.finished_dealing is True
    assert game_player.making_decision is True
    assert game_player.decision_time is not None


@pytest.mark.asyncio
async def test_dealing_card_on_seven_seats(betting_manager):
    await betting_manager.charge_user(10, 1)
    await betting_manager.charge_user(15, 3)
    await betting_manager.charge_user(15, 5)
    await betting_manager.charge_user(25, 7)
    await betting_manager.charge_user(10, 9)
    await betting_manager.charge_user(10, 11)
    await betting_manager.charge_user(20, 13)
    await get_round_and_finish_betting_time()
    user_session_data = await redis_cache.redis_cache.hgetall("test_sid")
    card_manager = EuropeanCardsManager(user_session_data, TEST_ROUND_ID)
    await scan_multiple_cards(
        [
            "12C",
            "19S",
            "1JD",
            "1QS",
            "1AS",
            "13S",
            "1TS",
            "12D",
            "13D",
            "19C",
            "18H",
            "17S",
            "17H",
            "15H",
            "15D",
        ],
        card_manager,
    )
    game_player: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    second_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.seat_number == 3
    )
    third_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.seat_number == 5
    )
    fourth_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.seat_number == 7
    )
    fifth_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.seat_number == 9
    )
    sixth_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.seat_number == 11
    )
    seventh_game_player: GamePlayer = await GamePlayer.find_one(
        GamePlayer.seat_number == 13
    )
    game_round: GameRound = await GameRound.find_one({})
    assert game_player.cards == ["12C", "13D"]
    assert second_game_player.cards == ["19S", "19C"]
    assert third_game_player.cards == ["1JD", "18H"]
    assert fourth_game_player.cards == ["1QS", "17S"]
    assert fifth_game_player.cards == ["1AS", "17H"]
    assert sixth_game_player.cards == ["13S", "15H"]
    assert seventh_game_player.cards == ["1TS", "15D"]
    assert game_round.dealer_cards == ["12D"]
    assert game_round.finished_dealing is True
    assert game_player.making_decision is True
    assert game_player.decision_time is not None


@pytest.mark.asyncio
async def test_dealing_cards_more_than_allowed(betting_manager):
    await betting_manager.charge_user(10, 1)
    await get_round_and_finish_betting_time()
    user_session_data = await redis_cache.redis_cache.hgetall("test_sid")
    card_manager = EuropeanCardsManager(user_session_data, TEST_ROUND_ID)
    with pytest.raises(ValidationError) as error:
        await scan_multiple_cards(["12C", "15H", "15D", "1AD", "18S"], card_manager)
        assert str(error) == "Dealer already has one card"
    game_player: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    game_round: GameRound = await GameRound.find_one({})
    assert game_player.cards == ["12C", "15D"]
    assert game_round.dealer_cards == ["15H"]


@pytest.mark.asyncio
async def test_dealing_cards_on_seats_1_3_4(betting_manager):
    await betting_manager.charge_user(10, 1)
    await betting_manager.charge_user(20, 5)
    await betting_manager.charge_user(50, 7)

    await get_round_and_finish_betting_time()
    user_session_data = await redis_cache.redis_cache.hgetall("test_sid")
    card_manager = EuropeanCardsManager(user_session_data, TEST_ROUND_ID)
    await scan_multiple_cards(
        ["12C", "15H", "15D", "1TD", "18S", "19C", "1JD"], card_manager
    )
    game_player_1: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    game_player_3: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 5)
    game_player_4: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 7)
    game_round: GameRound = await GameRound.find_one({})
    assert game_player_1.cards == ["12C", "18S"]
    assert game_player_3.cards == ["15H", "19C"]
    assert game_player_4.cards == ["15D", "1JD"]
    assert game_round.dealer_cards == ["1TD"]
    assert game_round.finished_dealing is True
    assert game_player_1.making_decision is True
    assert game_player_1.decision_time is not None


@pytest.mark.asyncio
async def test_dealing_cards_on_seats_5_6_7(betting_manager):
    await betting_manager.charge_user(10, 9)
    await betting_manager.charge_user(10, 11)
    await betting_manager.charge_user(15, 13)

    await get_round_and_finish_betting_time()
    user_session_data = await redis_cache.redis_cache.hgetall("test_sid")
    card_manager = EuropeanCardsManager(user_session_data, TEST_ROUND_ID)
    await scan_multiple_cards(
        ["12C", "15H", "15D", "1TD", "18S", "19C", "1JD"], card_manager
    )
    game_player_5: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 9)
    game_player_6: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 11)
    game_player_7: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 13)
    game_round: GameRound = await GameRound.find_one({})
    assert game_player_5.cards == ["12C", "18S"]
    assert game_player_6.cards == ["15H", "19C"]
    assert game_player_7.cards == ["15D", "1JD"]
    assert game_round.dealer_cards == ["1TD"]
    assert game_player_5.making_decision is True
    assert game_player_5.decision_time is not None


@pytest.mark.asyncio
async def test_dealing_cards_on_seats_3_6_7(betting_manager):
    await betting_manager.charge_user(10, 5)
    await betting_manager.charge_user(20, 11)
    await betting_manager.charge_user(40, 13)

    await get_round_and_finish_betting_time()
    user_session_data = await redis_cache.redis_cache.hgetall("test_sid")
    card_manager = EuropeanCardsManager(user_session_data, TEST_ROUND_ID)
    await scan_multiple_cards(
        ["12C", "15H", "15D", "1TD", "18S", "19C", "1JD"], card_manager
    )
    game_player_3: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 5)
    game_player_6: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 11)
    game_player_7: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 13)
    game_round: GameRound = await GameRound.find_one({})
    assert game_player_3.cards == ["12C", "18S"]
    assert game_player_6.cards == ["15H", "19C"]
    assert game_player_7.cards == ["15D", "1JD"]
    assert game_round.dealer_cards == ["1TD"]
    assert game_player_3.making_decision is True
    assert game_player_3.decision_time is not None


@pytest.mark.asyncio
async def test_dealing_cards_on_seats_1_4_6_7(betting_manager):
    await betting_manager.charge_user(10, 1)
    await betting_manager.charge_user(10, 7)
    await betting_manager.charge_user(50, 11)
    await betting_manager.charge_user(10, 13)

    await get_round_and_finish_betting_time()
    user_session_data = await redis_cache.redis_cache.hgetall("test_sid")
    card_manager = EuropeanCardsManager(user_session_data, TEST_ROUND_ID)
    await scan_multiple_cards(
        ["12C", "15H", "15D", "1AD", "18S", "19C", "1JD", "17H", "13H"], card_manager
    )
    game_player_1: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    game_player_4: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 7)
    game_player_6: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 11)
    game_player_7: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 13)
    game_round: GameRound = await GameRound.find_one({})
    assert game_player_1.cards == ["12C", "19C"]
    assert game_player_4.cards == ["15H", "1JD"]
    assert game_player_6.cards == ["15D", "17H"]
    assert game_player_7.cards == ["1AD", "13H"]
    assert game_round.dealer_cards == ["18S"]
    assert game_player_1.making_decision is True
    assert game_player_1.decision_time is not None


@pytest.mark.asyncio
async def test_dealing_cards_on_seats_1_3_4_6_7(betting_manager):
    await betting_manager.charge_user(10, 1)
    await betting_manager.charge_user(10, 5)
    await betting_manager.charge_user(50, 7)
    await betting_manager.charge_user(15, 11)
    await betting_manager.charge_user(20, 13)

    await get_round_and_finish_betting_time()
    user_session_data = await redis_cache.redis_cache.hgetall("test_sid")
    card_manager = EuropeanCardsManager(user_session_data, TEST_ROUND_ID)
    await scan_multiple_cards(
        ["12C", "15H", "15D", "1AD", "18S", "19C", "1JD", "17H", "13H", "16D", "16S"],
        card_manager,
    )
    game_player_1: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 1)
    game_player_3: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 5)
    game_player_4: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 7)
    game_player_6: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 11)
    game_player_7: GamePlayer = await GamePlayer.find_one(GamePlayer.seat_number == 13)
    game_round: GameRound = await GameRound.find_one({})
    assert game_player_1.cards == ["12C", "1JD"]
    assert game_player_3.cards == ["15H", "17H"]
    assert game_player_4.cards == ["15D", "13H"]
    assert game_player_6.cards == ["1AD", "16D"]
    assert game_player_7.cards == ["18S", "16S"]
    assert game_round.dealer_cards == ["19C"]
    assert game_player_1.making_decision is True
    assert game_player_1.decision_time is not None


@pytest.mark.asyncio
async def test_dealing_card_on_two_seats_skip_dealer_scan(betting_manager):
    await betting_manager.charge_user(20, 1)
    await betting_manager.charge_user(10, 3)
    await get_round_and_finish_betting_time()
    user_session_data = await redis_cache.redis_cache.hgetall("test_sid")
    card_manager = EuropeanCardsManager(user_session_data, TEST_ROUND_ID)
    await scan_multiple_cards(["1AC", "1AS", "17D", "1TS", "2TS"], card_manager)
    game_round: GameRound = await GameRound.find_one({})
    assert len(game_round.dealer_cards) == 1
    assert game_round.finished_dealing is True


@pytest.mark.asyncio
async def test_dealing_cards_before_betting_time_is_over(betting_manager):
    await betting_manager.charge_user(10, 1)
    user_session_data = await redis_cache.redis_cache.hgetall("test_sid")
    card_manager = EuropeanCardsManager(user_session_data, TEST_ROUND_ID)
    with pytest.raises(ValidationError) as error:
        await scan_multiple_cards(["12C", "15H", "16C"], card_manager)
        assert str(error) == "Betting time is not over"


@pytest.mark.asyncio
async def test_dealing_card_when_player_is_making_decision(betting_manager):
    await betting_manager.charge_user(10, 1)
    await get_round_and_finish_betting_time()
    user_session_data = await redis_cache.redis_cache.hgetall("test_sid")
    action_card_manager = ActionCardManager(user_session_data, TEST_ROUND_ID)
    card_manager = EuropeanCardsManager(user_session_data, TEST_ROUND_ID)
    await scan_multiple_cards(["12C", "13C", "14C"], card_manager)
    with pytest.raises(ValidationError) as error:
        await action_card_manager.scan_card("15C")
        assert str(error) == "Can not scan card when player is making a decision"
