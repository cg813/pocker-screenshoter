import asyncio
from asyncio import exceptions

import pytest

from apps.game.services.connect_manager import ConnectManager

from ..helpers import (
    TEST_GAME_ID,
    base_helper,
    connect_socket,
    get_round_and_finish_betting_time,
    mock_check_if_user_can_connect,
)


@pytest.mark.asyncio
async def test_getting_rollback_status_on_making_rollback(monkeypatch):
    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )

    _, client = await connect_socket(TEST_GAME_ID, "test_sid")

    await base_helper(
        client,
        "bet_status",
        "place_bet",
        {"seat_number": 1, "amount": 10, "bet_type": "bet"},
    )
    await base_helper(
        client,
        "rollback_status",
        "make_rollback",
        {"seat_number": 1, "rollback_type": "bet"},
    )
    await client.disconnect()


@pytest.mark.asyncio
async def test_not_getting_new_rollback_event_to_rollback_maker(monkeypatch):
    new_rollback_future = asyncio.get_running_loop().create_future()
    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )

    _, client = await connect_socket(TEST_GAME_ID, "test_sid")

    @client.event
    def new_rollback(data):
        new_rollback_future.set_result(data)

    await base_helper(
        client,
        "bet_status",
        "place_bet",
        {"seat_number": 1, "amount": 10, "bet_type": "bet"},
    )

    await client.emit("make_rollback", {"seat_number": 1, "rollback_type": "bet"})

    try:
        await asyncio.wait_for(new_rollback_future, timeout=0.2)
        assert False
    except exceptions.TimeoutError:
        assert True

    await client.disconnect()


@pytest.mark.asyncio
async def test_getting_new_rollback_event_by_other_player(monkeypatch):
    new_rollback_future = asyncio.get_running_loop().create_future()
    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )

    _, client1 = await connect_socket(TEST_GAME_ID, "test_sid1")
    _, client2 = await connect_socket(TEST_GAME_ID, "test_sid2")

    @client2.event
    def new_rollback(data):
        new_rollback_future.set_result(data)

    await base_helper(
        client1,
        "bet_status",
        "place_bet",
        {"seat_number": 1, "amount": 10, "bet_type": "bet"},
    )

    await client1.emit("make_rollback", {"seat_number": 1, "rollback_type": "bet"})

    new_rollback_data = await asyncio.wait_for(new_rollback_future, timeout=2)

    assert int(new_rollback_data["seat_number"]) == 1
    assert new_rollback_data.get("rollback_type") == "bet"

    await client1.disconnect()
    await client2.disconnect()


@pytest.mark.asyncio
async def test_rollback_without_placing_bet(monkeypatch):
    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )
    _, client = await connect_socket(TEST_GAME_ID, "test_sid")

    error_data = await base_helper(
        client, "error", "make_rollback", {"seat_number": 1, "rollback_type": "bet"}
    )
    assert error_data.get("message") == "Player has not placed any bet yet"
    await client.disconnect()


@pytest.mark.asyncio
async def test_rollback_when_rollback_time_is_over(monkeypatch):
    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )
    _, client = await connect_socket(TEST_GAME_ID, "test_sid")

    await base_helper(
        client,
        "bet_status",
        "place_bet",
        {"seat_number": 1, "amount": 10, "bet_type": "bet"},
    )
    await get_round_and_finish_betting_time()
    error_data = await base_helper(
        client, "error", "make_rollback", {"seat_number": 1, "rollback_type": "bet"}
    )
    assert error_data.get("message") == "Rollback time is over"
    await client.disconnect()


@pytest.mark.asyncio
async def test_rollback_when_there_is_no_bet_to_rollback(monkeypatch):
    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )
    _, client = await connect_socket(TEST_GAME_ID, "test_sid")

    await base_helper(
        client,
        "bet_status",
        "place_bet",
        {"seat_number": 1, "amount": 10, "bet_type": "bet"},
    )
    await base_helper(
        client,
        "rollback_status",
        "make_rollback",
        {"seat_number": 1, "rollback_type": "bet"},
    )
    error_data = await base_helper(
        client, "error", "make_rollback", {"seat_number": 1, "rollback_type": "bet"}
    )
    assert error_data.get("message") == "There is no bet to rollback"
    await client.disconnect()
