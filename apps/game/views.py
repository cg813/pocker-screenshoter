import os
import re
from typing import List

from fastapi import APIRouter, Depends, Response

from apps.connections import redis_cache
from apps.game.consumers import external_sio
from apps.game.queries import get_game, get_game_player, get_merchant
from apps.game.tasks import start_new_round

from .documents import Game, GameRound, Merchant, GamePlayer
from .models import MerchantBackOfficeModel, GameUpdateModel, GameMerchantModel
from .services.permissions import check_merchant_permissions
from apps.game.services.auth import check_token

router = APIRouter()


@router.post("/create/game/", status_code=201)
async def create_game(game_data: Game):
    await game_data.create()
    return game_data


@router.get("/get/games/", status_code=200, response_model=List[Game])
async def get_games():
    return await Game.find_all().to_list()


@router.get("/get/game/{game_id}", status_code=200, response_model=Game)
async def get_single_game(game: Game = Depends(get_game)):
    return game


@router.post("/update/game/{game_id}", status_code=200, response_model=Game)
async def update_game(new_data: GameUpdateModel, game: Game = Depends(get_game)):
    game.name = new_data.name
    game.game_status = new_data.game_status
    game.is_break = new_data.is_break
    game.table_stream_key_1 = new_data.table_stream_key_1
    game.table_stream_key_2 = new_data.table_stream_key_2
    game.type = new_data.type
    return await game.save()


@router.get("/get/game/url/")
async def get_game_url(
    game_id: str, user_token: str, merchant_id=Depends(check_merchant_permissions)
):
    await redis_cache.set(user_token, merchant_id)
    return {
        "game_url": f"{os.environ.get('CLIENT_GAME_URL')}/player/{game_id}/{user_token}/"
    }


@router.get("/get/game/url/dealer/")
async def get_game_url_for_dealer(game_id: str, _=Depends(check_token)):
    return {"game_url": f"{os.environ.get('DEALER_GAME_URL')}/game/{game_id}"}


@router.post(
    "/create/merchant/", status_code=201, response_model=MerchantBackOfficeModel
)
async def create_merchant(merchant: Merchant):
    return await merchant.create()


@router.get("/get/merchants/", response_model=List[MerchantBackOfficeModel])
async def get_all_merchants():
    return await Merchant.find_all().project(MerchantBackOfficeModel).to_list()


@router.post(
    "/merchants/add_game/{merchant_id}",
    status_code=200,
    response_model=MerchantBackOfficeModel,
)
async def add_new_game_to_merchant(
    new_data: GameMerchantModel,
    merchant: Merchant = Depends(get_merchant),
):

    await Merchant.get_motor_collection().find_one_and_update(
        {"_id": merchant.id},
        {
            "$push": {
                "games": {
                    "game_id": new_data.game_id,
                    "game_name": new_data.game_name,
                    "min_bet": new_data.min_bet,
                    "max_bet": new_data.max_bet,
                    "bet_range": new_data.bet_range,
                    "decision_make_time": new_data.decision_make_time,
                    "is_active": new_data.is_active,
                }
            }
        },
    )

    return await Merchant.find_one(Merchant.id == merchant.id)


@router.post(
    "/merchants/update_game/{merchant_id}/{game_id}",
    status_code=200,
    response_model=MerchantBackOfficeModel,
)
async def update_merchant_game(
    new_data: GameMerchantModel,
    merchant: Merchant = Depends(get_merchant),
    game: Game = Depends(get_game),
):

    new_data.game_id = str(game.id)
    await Merchant.get_motor_collection().find_one_and_update(
        {"_id": merchant.id, "games.game_id": new_data.game_id},
        {
            "$set": {
                "games.$": {
                    "game_id": new_data.game_id,
                    "game_name": new_data.game_name,
                    "min_bet": new_data.min_bet,
                    "max_bet": new_data.max_bet,
                    "bet_range": new_data.bet_range,
                    "decision_make_time": new_data.decision_make_time,
                    "is_active": new_data.is_active,
                }
            }
        },
    )

    return await Merchant.find_one(Merchant.id == merchant.id)


@router.get("/round/get_with_round_id/{round_id}")
async def get_round_with_round_id(round_id):
    game_round = await GameRound.get_motor_collection().find_one(
        {"round_id": re.compile(round_id, re.IGNORECASE)}
    )
    if game_round:
        game_round["_id"] = str(game_round["_id"])
        return game_round


@router.get("/change_dealer/{game_id}/{dealer_name}")
async def change_dealer(game_id, dealer_name):
    await redis_cache.set(f"{game_id}:dealer_name", dealer_name)
    await external_sio.emit(
        "change_dealer",
        {
            "dealer_name": dealer_name,
        },
        room=game_id,
    )

    return Response(status_code=200)


@router.post("/open/game/{game_id}", status_code=200)
async def open_game(game_id: str):
    game = await get_game(game_id)
    game.is_open = True
    await game.save()

    await GameRound.get_motor_collection().update_many(
        {"game_id": game_id, "finished": False}, {"$set": {"finished": True}}
    )
    start_new_round.apply_async(args=[game_id])


@router.get("/players/active/{game_id}", status_code=200)
async def get_active_players(game: Game = Depends(get_game)):
    return (
        await GamePlayer.find(
            GamePlayer.game_id == str(game.id), GamePlayer.archived == False
        )
        .sort(-GamePlayer.updated_at)
        .to_list()
    )


@router.put("/players/archive/{game_player_id}")
async def archieve_game_player_with_id(
    game_player: GamePlayer = Depends(get_game_player),
):
    game_player.archived = True
    return await game_player.save()


@router.get("/reset")
async def reset_db():
    await GameRound.get_motor_collection().drop()
    await GamePlayer.get_motor_collection().drop()
    await redis_cache.flush_db()


@router.get("/health")
async def health_check():
    return {"message": "success"}
