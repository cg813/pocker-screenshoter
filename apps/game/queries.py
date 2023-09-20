from beanie import PydanticObjectId
from fastapi import HTTPException

from .documents import Game, Merchant, GamePlayer


async def get_game(game_id: str) -> Game:
    game = await Game.get(PydanticObjectId(game_id))
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return game


async def get_merchant(merchant_id: str) -> Merchant:
    merchant = await Merchant.get(PydanticObjectId(merchant_id))
    if merchant is None:
        raise HTTPException(status_code=404, detail="Merchant was not found")
    return merchant


async def get_game_player(game_player_id: str) -> GamePlayer:
    game_player = await GamePlayer.get(PydanticObjectId(game_player_id))
    if game_player is None:
        raise HTTPException(status_code=404, detail="GamePlayer not found")
    return game_player
