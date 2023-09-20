import asyncio
from asyncio import exceptions

import pytest

from apps.game.documents import GameRound
from apps.game.services.connect_manager import ConnectManager

from ..helpers import (
    TEST_GAME_ID,
    base_helper,
    connect_socket,
    get_round_and_finish_betting_time,
    mock_check_if_user_can_connect,
)


@pytest.mark.asyncio
async def test_getting_start_timer_event_on_placing_bet(monkeypatch, betting_manager):
    game_round = await GameRound.find_one({})
    game_round.start_timestamp = None
    await game_round.save()
    start_timer_future = asyncio.get_running_loop().create_future()
    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )

    on_connect_data, client = await connect_socket(TEST_GAME_ID, "test_sid")

    @client.event
    def start_timer(data):
        start_timer_future.set_result(data)

    await betting_manager.charge_user(10, 1)
    await asyncio.wait_for(start_timer_future, timeout=2)
    await betting_manager.charge_user(10, 1)
    await client.disconnect()


@pytest.mark.asyncio
async def test_getting_bet_status_on_placing_bet(monkeypatch):
    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )

    _, client = await connect_socket(TEST_GAME_ID, "test_sid")

    bet_data = await base_helper(
        client,
        "bet_status",
        "place_bet",
        {"seat_number": 1, "amount": 10, "bet_type": "bet"},
    )
    assert "seat_number" in bet_data
    await client.disconnect()


@pytest.mark.asyncio
async def test_not_getting_new_bet_group_event_to_bet_maker(monkeypatch):
    new_bet_future = asyncio.get_running_loop().create_future()
    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )

    on_connect_data, client = await connect_socket(TEST_GAME_ID, "test_sid")

    @client.event
    def new_bet(data):
        new_bet_future.set_result(data)

    await client.emit("place_bet", {"seat_number": 1, "amount": 10, "bet_type": "bet"})

    try:
        await asyncio.wait_for(new_bet_future, timeout=0.2)
        assert False
    except exceptions.TimeoutError:
        assert True

    await client.disconnect()


@pytest.mark.asyncio
async def test_getting_new_bet_group_event_by_other_player(monkeypatch):
    new_bet_future = asyncio.get_running_loop().create_future()
    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )

    _, client1 = await connect_socket(TEST_GAME_ID, "test_sid1")
    _, client2 = await connect_socket(TEST_GAME_ID, "test_sid2")

    @client2.event
    def new_bet(data):
        new_bet_future.set_result(data)

    await client1.emit("place_bet", {"seat_number": 1, "amount": 10, "bet_type": "bet"})

    new_bet_data = await asyncio.wait_for(new_bet_future, timeout=2)

    assert new_bet_data.get("bet_type") == "bet"
    assert new_bet_data.get("seat_number") == 1
    assert new_bet_data.get("total_bet") == 10

    await client1.disconnect()
    await client2.disconnect()


@pytest.mark.asyncio
async def test_making_bet_on_out_of_range_seat(monkeypatch):
    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )
    _, client = await connect_socket(TEST_GAME_ID, "test_sid")

    error_data = await base_helper(
        client,
        "error",
        "place_bet",
        {"seat_number": 8, "amount": 10, "bet_type": "bet"},
    )
    assert error_data.get("message") == "seat number out of range"
    await client.disconnect()


@pytest.mark.asyncio
async def test_making_negative_bet_amount(monkeypatch):
    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )
    _, client = await connect_socket(TEST_GAME_ID, "test_sid")

    error_data = await base_helper(
        client,
        "error",
        "place_bet",
        {"seat_number": 8, "amount": -10, "bet_type": "bet"},
    )
    assert error_data.get("message") == "Unsupported amount"
    await client.disconnect()


@pytest.mark.asyncio
async def test_making_bet_when_betting_time_is_ovet(monkeypatch):
    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )
    _, client = await connect_socket(TEST_GAME_ID, "test_sid")

    await get_round_and_finish_betting_time()
    error_data = await base_helper(
        client,
        "error",
        "place_bet",
        {"seat_number": 1, "amount": 10, "bet_type": "bet"},
    )
    assert error_data.get("message") == "betting time is over"
    await client.disconnect()


@pytest.mark.asyncio
async def test_making_bet_less_than_maximum_amount(monkeypatch):
    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )
    _, client = await connect_socket(TEST_GAME_ID, "test_sid")

    error_data = await base_helper(
        client, "error", "place_bet", {"seat_number": 1, "amount": 5, "bet_type": "bet"}
    )
    assert error_data.get("message") == "placing less than minimum bet is not allowed"
    await client.disconnect()


@pytest.mark.asyncio
async def test_making_bet_more_than_maximum_amount(monkeypatch):
    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )
    _, client = await connect_socket(TEST_GAME_ID, "test_sid")

    error_data = await base_helper(
        client,
        "error",
        "place_bet",
        {"seat_number": 1, "amount": 300, "bet_type": "bet"},
    )
    assert error_data.get("message") == "placing more than maximum bet is not allowed"
    await client.disconnect()
