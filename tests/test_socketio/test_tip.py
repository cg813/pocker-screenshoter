import pytest
import httpx

from apps.game.services.connect_manager import ConnectManager
from apps.game.services.custom_exception import ValidationError


from ..helpers import (
    TEST_GAME_ID,
    TEST_MERCHANT_ID,
    TEST_SESSION_DATA,
    base_helper,
    connect_socket,
    mock_check_if_user_can_connect,
    mock_httpx_bad_request,
    mock_httpx_request,
)


@pytest.mark.asyncio
async def test_tip_status_on_making_tip(monkeypatch):
    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_httpx_request)
    _, client = await connect_socket(TEST_GAME_ID, "test_sid")
    tip_data = await base_helper(
        client,
        "tip_status",
        "tip_dealer",
        {"amount": 10},
    )
    assert tip_data == {
        "user_deposit": 980,
        "player_id": f"{TEST_SESSION_DATA['user_id']}{TEST_MERCHANT_ID}",
    }
    await client.disconnect()


@pytest.mark.asyncio
async def test_tip_status_when_unable_to_tip(monkeypatch):
    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_httpx_bad_request)
    _, client = await connect_socket(TEST_GAME_ID, "test_sid")
    error = await base_helper(
        client,
        "error",
        "tip_dealer",
        {"amount": 10},
    )
    error == {"message": "Can not tip the dealer"}
    await client.disconnect()


@pytest.mark.asyncio
async def test_message_in_chat_when_player_tips(monkeypatch):
    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_httpx_request)
    _, client = await connect_socket(TEST_GAME_ID, "test_sid")
    message_data = await base_helper(
        client,
        "send_chat_message",
        "tip_dealer",
        {"amount": 10},
    )
    assert message_data == {
        "player": "MIMA",
        "message": f"{TEST_SESSION_DATA['user_name']} tipped dealer ${10}",
    }
    await client.disconnect()


@pytest.mark.asyncio
async def test_tip_with_negative_amount(monkeypatch):
    monkeypatch.setattr(
        ConnectManager, "_check_if_user_can_connect", mock_check_if_user_can_connect
    )
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_httpx_request)
    _, client = await connect_socket(TEST_GAME_ID, "test_sid")

    error_data = await base_helper(
        client,
        "error",
        "tip_dealer",
        {"amount": -10},
    )

    assert error_data.get("message") == "Unsupported amount"
    await client.disconnect()
