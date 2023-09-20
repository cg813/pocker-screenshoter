""" This module is for making http request to Core api for example: getting user balance, place some bets etc. """
import httpx

from apps.game.services.custom_exception import ValidationError
from apps.game.services.schema_generator import (
    generate_authentication_request_data,
    inflect_response_data,
)


async def validate_user_token(token: str, merchant_data: dict):  # pragma: no cover
    """This function is checking if token is valid for the game.
    :param token is Random generated string by the Merchant.
    :param merchant_check_url is a dictionary representation of merchant data from redis.
    """
    data = generate_authentication_request_data(token, merchant_data["schema_type"])
    async with httpx.AsyncClient() as client:
        resp = await client.post(merchant_data["validate_token_url"], json=data)
        response = inflect_response_data(resp.json())
        if resp.status_code != 200 or response["status"].lower() == "failed":
            raise ValidationError("Can not validate user token please try again")
        return resp.json()


async def send_data_to_merchant(url, data):
    transport = httpx.AsyncHTTPTransport(retries=5)
    async with httpx.AsyncClient(transport=transport) as client:
        resp = await client.post(url, json=data)
        print(resp.json())
        return resp.status_code, inflect_response_data(resp.json())
