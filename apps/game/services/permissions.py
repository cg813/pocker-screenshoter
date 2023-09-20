from fastapi import HTTPException, Request

from apps.game.documents import Merchant


async def check_merchant_permissions(game_id: str, request: Request):
    """This function checks if merchant has permission to access game table"""
    if merchant := await Merchant.find_one(
        {
            "api_key": request.headers.get("api-key"),
            "games.game_id": game_id,
            "games.is_active": True,
        }
    ):
        return str(merchant.id)
    raise HTTPException(status_code=403, detail="something went wrong")
