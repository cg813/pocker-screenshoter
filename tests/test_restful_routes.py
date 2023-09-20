import pytest

from .helpers import TEST_GAME_ID


@pytest.mark.asyncio
async def test_create_game_route(client):
    response = await client.post(
        "/create/game/",
        json={
            "name": "string",
            "game_status": True,
            "type": "european",
            "is_break": False,
            "table_stream_key_1": "string",
            "table_stream_key_2": "string",
        },
    )
    response_data = response.json()
    del response_data["_id"]
    del response_data["created_at"]
    del response_data["updated_at"]
    assert response.status_code == 201
    assert response_data == {
        "name": "string",
        "game_status": True,
        "type": "european",
        "is_break": False,
        "is_open": False,
        "table_stream_key_1": "string",
        "table_stream_key_2": "string",
    }


@pytest.mark.asyncio
async def test_get_games_route(client):
    res = await client.get("/get/games/")
    response_data = res.json()
    assert res.status_code == 200
    assert len(response_data) > 0
    assert "name" in response_data[0]
    assert "game_status" in response_data[0]
    assert "table_stream_key_1" in response_data[0]
    assert "table_stream_key_2" in response_data[0]


@pytest.mark.asyncio
async def test_get_single_game(client):
    res = await client.get(f"/get/game/{TEST_GAME_ID}")

    response_data = res.json()
    del response_data["created_at"]
    del response_data["updated_at"]
    assert response_data == {
        "_id": TEST_GAME_ID,
        "name": "test_game",
        "type": "european",
        "game_status": True,
        "is_break": False,
        "is_open": False,
        "table_stream_key_1": "123",
        "table_stream_key_2": "456",
    }
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_create_merchant(client):
    res = await client.post(
        "/create/merchant/",
        json={
            "name": "string",
            "games": [
                {
                    "game_id": "string",
                    "game_name": "string",
                    "min_bet": 1,
                    "max_bet": 200,
                    "bet_range": [1, 5, 10, 20],
                    "decision_make_time": 15,
                    "is_active": True,
                }
            ],
            "transaction_url": "http://backend:8000/api/games/transaction/",
            "validate_token_url": "http://backend:8000/api/games/check/",
            "bet_url": "http://backend:8000/api/games/check/",
            "win_url": "http://backend:8000/api/games/check/",
            "rollback_url": "http://backend:8000/api/games/check/",
            "get_balance_url": "http://backend:8000/api/games/get_balance/",
            "schema_type": "snake",
        },
    )
    response_data = res.json()
    assert res.status_code == 201
    assert "name" in response_data
    assert "games" in response_data
    assert "transaction_url" in response_data
    assert "validate_token_url" in response_data
    assert "game_id" in response_data["games"][0]
    assert "min_bet" in response_data["games"][0]
    assert "max_bet" in response_data["games"][0]
    assert "bet_range" in response_data["games"][0]


@pytest.mark.asyncio
async def test_get_merchants(client):
    res = await client.get("/get/merchants/")
    assert res.status_code == 200
    assert len(res.json()) > 0


@pytest.mark.asyncio
async def test_get_game_url_without_api_key(client):
    res = await client.get(
        f"/get/game/url/?game_id={TEST_GAME_ID}&user_token=test_token"
    )

    assert res.status_code == 403


@pytest.mark.asyncio
async def test_get_game_url_with_api_key(client):
    res = await client.get(
        f"/get/game/url/?game_id={TEST_GAME_ID}&user_token=test_token",
        headers={"api-key": "test_api_key"},
    )
    assert res.status_code == 200
    assert "game_url" in res.json()
