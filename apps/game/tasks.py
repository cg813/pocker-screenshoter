import json
import os

import redis
import requests
import socketio
from uuid import uuid4
from bson import ObjectId
from celery import shared_task
from pymongo import MongoClient

from apps.config import settings
from apps.game.services.utils import (
    get_timestamp,
    id_generator,
    get_time_left_in_seconds,
    check_should_not_move_to_next_game_player,
    check_if_player_can_double_or_split,
)
from apps.game.services.schema_generator import (
    generate_bet_request_data,
    inflect_response_data,
    generate_win_request_data,
)
from apps.game.cards.hand import Hand


external_sio = socketio.RedisManager(
    settings.WS_MESSAGE_QUEUE, write_only=True, logger=True
)
client = MongoClient(os.environ.get("BLACKJACK_MONGODB_URL"))
db = client[settings.DATABASE_NAME]
r = redis.Redis(
    host=settings.REDIS_HOST_NAME,
    port=6379,
    db=4,
    encoding="utf-8",
    decode_responses=True,
)


@shared_task
def send_bet_to_merchant_and_update_game_player(
    bet_url: str, game_player: dict, schema_type: str
):
    bet_external_id = str(uuid4())
    send_data = generate_bet_request_data(
        schema_type, game_player["total_bet"], game_player, bet_external_id
    )
    response = requests.post(bet_url, json=send_data)
    if response.status_code == 200:
        data = inflect_response_data(response.json())
        if data["status"].lower() == "ok":
            db.GamePlayer.find_one_and_update(
                {"_id": ObjectId(game_player["_id"])},
                {"$set": {"external_ids.bet": bet_external_id}},
            )
            r.set(
                f"{game_player['user_id']}:{game_player['merchant']}",
                data["total_balance"],
            )
        else:
            db.GamePlayer.find_one_and_update(
                {"_id": ObjectId(game_player["_id"])},
                {
                    "$set": {
                        "archived": True,
                        "detail": "insufficient_balance",
                        "rejected": True,
                    }
                },
            )

            external_sio.emit(
                "insufficient_balance",
                {
                    "message": "Not enough funds to place bet",
                    "balance": data["total_balance"],
                },
                room=game_player["sid"],
            )
            r.set(
                f"{game_player['user_id']}:{game_player['merchant']}",
                data["total_balance"],
            )


@shared_task
def send_winning_to_merchant_and_update_game_player(
    game_player: dict, win_url: str, win: float, round_data: dict, schema_type: str
):
    win_external_id = str(uuid4())
    send_data = generate_win_request_data(
        schema_type, win, game_player, win_external_id
    )
    response = requests.post(win_url, json=send_data)

    if response.status_code == 200:
        data = inflect_response_data(response.json())
        if data["status"].lower() == "ok":
            db.GamePlayer.find_one_and_update(
                {"_id": ObjectId(game_player["_id"])},
                {
                    "$set": {
                        "winning_amount": win,
                        "archived": True,
                        "deposit": game_player["deposit"] + win,
                        "external_ids.win": win_external_id,
                    }
                },
            )

            r.set(
                f"{game_player['user_id']}:{game_player['merchant']}",
                data["total_balance"],
            )
            external_sio.emit(
                "result",
                {
                    "type": "win",
                    "seat_number": game_player["seat_number"],
                    "winning_amount": win,
                },
                room=game_player["game_id"],
            )

            external_sio.emit(
                "update_balance",
                {
                    "balance": data["total_balance"],
                    "game_history": {
                        "action_list": game_player["action_list"],
                        "cards": game_player["cards"],
                        "game_round": round_data,
                        "insured": game_player["insured"],
                        # "join_game_at": game_player['join_game_at'],
                        "seat_number": game_player["seat_number"],
                        "total_bet": game_player["total_bet"],
                        "bet": game_player["bet"],
                        "bet_21_3": game_player["bet_21_3"],
                        "bet_21_3_combination": game_player["bet_21_3_combination"],
                        "bet_perfect_pair": game_player["bet_perfect_pair"],
                        "bet_perfect_pair_combination": game_player[
                            "bet_perfect_pair_combination"
                        ],
                        "user_name": game_player["user_name"],
                        "winning_amount": win,
                    },
                },
                room=game_player["sid"],
            )


@shared_task
def send_push_to_merchant_and_update_game_player(
    game_player: dict, win_url: str, win: float, round_data: dict, schema_type: str
):
    win_external_id = str(uuid4())
    send_data = generate_win_request_data(
        schema_type, win, game_player, win_external_id
    )
    response = requests.post(win_url, json=send_data)

    if response.status_code == 200:
        data = inflect_response_data(response.json())
        if data["status"].lower() == "ok":
            db.GamePlayer.find_one_and_update(
                {"_id": ObjectId(game_player["_id"])},
                {
                    "$set": {
                        "winning_amount": win,
                        "archived": True,
                        "deposit": game_player["deposit"] + win,
                        "external_ids.win": win_external_id,
                    }
                },
            )
            external_sio.emit(
                "result",
                {
                    "type": "push",
                    "seat_number": game_player["seat_number"],
                    "winning_amount": win,
                },
                room=game_player["game_id"],
            )

            external_sio.emit(
                "update_balance",
                {
                    "balance": data["total_balance"],
                    "game_history": {
                        "action_list": game_player["action_list"],
                        "cards": game_player["cards"],
                        "game_round": round_data,
                        "insured": game_player["insured"],
                        # "join_game_at": game_player['join_game_at'],
                        "seat_number": game_player["seat_number"],
                        "total_bet": game_player["total_bet"],
                        "bet": game_player["bet"],
                        "bet_21_3": game_player["bet_21_3"],
                        "bet_21_3_combination": game_player["bet_21_3_combination"],
                        "bet_perfect_pair": game_player["bet_perfect_pair"],
                        "bet_perfect_pair_combination": game_player[
                            "bet_perfect_pair_combination"
                        ],
                        "user_name": game_player["user_name"],
                        "winning_amount": win,
                    },
                },
                room=game_player["sid"],
            )


@shared_task
def send_bets_to_merchant(game_round_id: str, game_id: str):
    merchants = db.Merchant.find(
        {"games.game_id": game_id}, {"_id": 1, "bet_url": 1, "schema_type": 1}
    )
    for merchant in merchants:
        bet_url = merchant["bet_url"]
        schema_type = merchant["schema_type"]
        game_players = db.GamePlayer.find(
            {"game_round": game_round_id, "merchant": str(merchant["_id"])}
        ).sort("seat_number")
        total_bet = 0
        players_repeat_data = {}
        for game_player in game_players:
            if game_player["bet"] > 0:
                total_bet += (
                    game_player["bet"]
                    + game_player["bet_21_3"]
                    + game_player["bet_perfect_pair"]
                )
                game_player["_id"] = str(game_player["_id"])
                send_bet_to_merchant_and_update_game_player.apply_async(
                    args=[bet_url, game_player, schema_type], max_retries=5
                )
                repeat_data = {
                    game_player["seat_number"]: {
                        "bet": game_player["bet"],
                        "bet_list": game_player["bet_list"],
                        "bet_21_3": game_player["bet_21_3"],
                        "bet_21_3_list": game_player["bet_21_3_list"],
                        "bet_perfect_pair": game_player["bet_perfect_pair"],
                        "bet_perfect_pair_list": game_player["bet_perfect_pair_list"],
                    }
                }
                repeat_cache_key = f"{game_player['user_id']}:{game_player['merchant']}:{game_player['game_round']}"
                if players_repeat_data.get(repeat_cache_key):
                    players_repeat_data[f"{repeat_cache_key}"].update(repeat_data)
                else:
                    players_repeat_data[f"{repeat_cache_key}"] = repeat_data

        if total_bet == 0:
            db.GameRound.find_one_and_update(
                {"_id": ObjectId(game_round_id)},
                {"$set": {"start_timestamp": None}},
            )
            external_sio.emit("repeat_betting", {}, room=game_id)
        else:
            for key, repeat_data in players_repeat_data.items():
                r.setex(
                    key,
                    settings.TIME_FOR_REPEAT_CACHE,
                    json.dumps(repeat_data),
                )


@shared_task
def start_new_round(game_id: str, prev_round_id: str = None, taken_seats: dict = {}):
    db.GameRound.update_many(
        {"finished": False, "game_id": game_id}, {"$set": {"finished": True}}
    )
    random_id = id_generator()
    game_round_id = db.GameRound.insert_one(
        {
            "created_at": get_timestamp(),
            "updated_at": get_timestamp(),
            "card_count": 0,
            "game_id": game_id,
            "round_id": random_id,
            "start_timestamp": None,
            "dealer_name": r.get(f"{game_id}:dealer_name"),
            "insurance_timestamp": None,
            "dealer_cards": [],
            "show_dealer_cards": False,
            "was_reset": False,
            "finished": False,
            "finished_dealing": False,
            "prev_round_id": prev_round_id,
        }
    ).inserted_id
    external_sio.emit(
        "start_new_round",
        {
            "next_round_real_id": str(game_round_id),
            "next_round_id": random_id,
            "seats": taken_seats,
        },
        room=game_id,
    )

    clean_all_seats_if_no_bets_are_placed.apply_async(
        args=[str(game_round_id)], countdown=17, max_retries=5
    )


@shared_task
def send_reset_to_merchant_and_update_game_player(
    send_data: dict, rollback_url: str, game_player: dict, bet_type: str, is_break=False
):
    response = requests.post(rollback_url, json=send_data)
    if response.status_code == 200:
        data = inflect_response_data(response.json())
        if data["status"].lower() == "ok":
            db.GamePlayer.find_one_and_update(
                {"_id": ObjectId(game_player["_id"])},
                {
                    "$set": {
                        f"external_ids.cancel_{bet_type}": game_player["external_ids"][
                            f"cancel_{bet_type}"
                        ],
                    }
                },
                return_document=True,
            )
            r.set(
                f"{game_player['user_id']}:{game_player['merchant']}",
                data["total_balance"],
            )
            external_sio.emit(
                "reset_status",
                {"balance": float(data["total_balance"]), "is_break": is_break},
                room=game_player["sid"],
            )

            external_sio.emit(
                "update_balance",
                {"balance": float(data["total_balance"])},
                room=f"{game_player['user_id']}:{game_player['merchant']}",
                skip_sid=game_player["sid"],
            )


@shared_task
def send_lose_event_and_game_player_history(
    game_player: dict, win_url: str, round_data: dict, schema_type: str
):
    win_external_id = str(uuid4())
    send_data = generate_win_request_data(schema_type, 0, game_player, win_external_id)
    response = requests.post(win_url, json=send_data)

    if response.status_code == 200:
        data = inflect_response_data(response.json())
        if data["status"].lower() == "ok":
            db.GamePlayer.find_one_and_update(
                {"_id": ObjectId(game_player["_id"])},
                {"$set": {"external_ids.win": win_external_id}},
            )

            r.set(
                f"{game_player['user_id']}:{game_player['merchant']}",
                data["total_balance"],
            )

            external_sio.emit(
                "result",
                {
                    "type": "lose",
                    "seat_number": game_player["seat_number"],
                    "winning_amount": 0,
                },
                room=game_player["game_id"],
            )

            external_sio.emit(
                "update_balance",
                {
                    "balance": data["total_balance"],
                    "game_history": {
                        "action_list": game_player["action_list"],
                        "cards": game_player["cards"],
                        "game_round": round_data,
                        "insured": game_player["insured"],
                        # "join_game_at": game_player['join_game_at'],
                        "seat_number": game_player["seat_number"],
                        "total_bet": game_player["total_bet"],
                        "bet": game_player["bet"],
                        "bet_21_3": game_player["bet_21_3"],
                        "bet_21_3_combination": game_player["bet_21_3_combination"],
                        "bet_perfect_pair": game_player["bet_perfect_pair"],
                        "bet_perfect_pair_combination": game_player[
                            "bet_perfect_pair_combination"
                        ],
                        "user_name": game_player["user_name"],
                        "winning_amount": 0,
                    },
                },
                room=game_player["sid"],
            )


def sync_get_next_player(game_player: dict) -> dict:
    seats = json.loads(r.get(f"{game_player['game_round']}:seats"))
    seat_id = seats.index(game_player["seat_number"])
    return db.GamePlayer.find_one_and_update(
        {"seat_number": seats[seat_id + 1], "game_round": game_player["game_round"]},
        {
            "$set": {
                "making_decision": True,
                "player_turn": True,
                "decision_time": get_timestamp(15),
            }
        },
        return_document=True,
    )


def sync_finish_player_turn(game_player_id: str):
    db.GamePlayer.find_one_and_update(
        {"_id": ObjectId(game_player_id)},
        {
            "$set": {
                "making_decision": False,
                "player_turn": False,
                "finished_turn": True,
            }
        },
    )


def send_decision_maker_event(game_player: dict):
    external_sio.emit(
        "decision_maker",
        {
            "seat_number": game_player["seat_number"],
            "decision_timer": game_player["decision_time"] - get_timestamp(),
        },
        room=game_player["game_id"],
    )


def sync_move_to_next_player(game_player_id: str, game_id: str, action_count: int):
    try:
        current_game_player = db.GamePlayer.find_one({"_id": ObjectId(game_player_id)})
        if check_should_not_move_to_next_game_player(current_game_player, action_count):
            return
        sync_finish_player_turn(game_player_id)
        next_game_player = sync_get_next_player(current_game_player)
        player_hand = Hand(next_game_player["cards"], next_game_player["last_action"])
        if not player_hand.can_continue_game():
            return sync_move_to_next_player(
                str(next_game_player["_id"]),
                game_id,
                len(next_game_player["action_list"]),
            )
        if next_game_player["is_active"] is False:
            wait_player.apply_async(
                args=[
                    str(next_game_player["_id"]),
                    game_id,
                    len(next_game_player["action_list"]),
                ],
                countdown=get_time_left_in_seconds(next_game_player["decision_time"])
                + 1,
            )
            db.GamePlayer.find_one_and_update(
                {"_id": ObjectId(next_game_player["_id"])},
                {"$set": {"inactivity_check_time": next_game_player["decision_time"]}},
            )
            send_decision_maker_event(next_game_player)
            return
        send_decision_maker_event(next_game_player)
        possible_action = player_hand.get_possible_player_actions()
        data_with_possible_action = check_if_player_can_double_or_split(
            next_game_player.deposit, next_game_player.bet, {"actions": possible_action}
        )
        external_sio.emit(
            "make_decision",
            {
                "cards": next_game_player["cards"],
                "score": player_hand.score,
                "actions": data_with_possible_action["actions"],
                "seat_number": next_game_player["seat_number"],
            },
            room=next_game_player["sid"],
        )
    except IndexError:
        game_round = db.GameRound.find_one_and_update(
            {"game_id": game_id, "finished": False},
            {"$set": {"finished_dealing": True, "show_dealer_cards": True}},
            return_document=True,
        )
        if Hand(game_round["dealer_cards"])._hand_scores.score >= 17:
            pay_winnings(game_id, game_round)
        else:
            dealer_hand = Hand(game_round["dealer_cards"])
            external_sio.emit(
                "dealer_score",
                {
                    "score": dealer_hand.get_score_repr(),
                    "cards": game_round["dealer_cards"],
                },
                room=game_id,
            )
            return external_sio.emit("scan_dealer_card", {}, room=game_id)


@shared_task()
def wait_player(game_player_id: str, game_id: str, action_count: int):
    sync_move_to_next_player(game_player_id, game_id, action_count)


@shared_task
def send_make_decision_to_starter_game_player(
    seats: list, seat_number_index: int, round_id: str, game_id: str
):
    try:
        starter_game_player = sync_get_starter_game_player(
            seats, seat_number_index, round_id
        )

        data, hand = Hand.generate_data(
            starter_game_player["cards"], starter_game_player["last_action"]
        )

        data_with_possible_action = check_if_player_can_double_or_split(
            starter_game_player["deposit"], starter_game_player["bet"], data
        )
        external_sio.emit(
            "make_decision", data_with_possible_action, room=starter_game_player["sid"]
        )

        external_sio.emit("make_decision", data, room=starter_game_player["sid"])
        external_sio.emit(
            "decision_maker",
            {
                "seat_number": starter_game_player["seat_number"],
                "decision_timer": starter_game_player["decision_time"]
                - get_timestamp(),
            },
            room=starter_game_player["game_id"],
        )
    except IndexError:
        external_sio.emit(
            "scan_dealer_card",
            {},
            room=game_id,
        )


def sync_get_starter_game_player(seats: list, seat_number_index: int, round_id: str):
    game_player: dict = db.GamePlayer.find_one(
        {
            "game_round": round_id,
            "seat_number": seats[seat_number_index],
            "bet": {"$gt": 0},
        }
    )

    if game_player["is_active"] is False:
        wait_player.apply_async(
            args=[
                str(game_player["_id"]),
                game_player["game_id"],
                len(game_player["action_list"]),
            ],
            countdown=settings.ACCEPT_BETS_SECONDS - 1,
        )

    if Hand(game_player["cards"]).can_continue_game():
        starter_game_player = db.GamePlayer.find_one_and_update(
            {
                "game_round": round_id,
                "seat_number": seats[seat_number_index],
                "bet": {"$gt": 0},
            },
            {
                "$set": {
                    "decision_time": get_timestamp(15),
                    "player_turn": True,
                    "making_decision": True,
                }
            },
            return_document=True,
        )
        return starter_game_player
    return sync_get_starter_game_player(seats, seat_number_index + 1, round_id)


@shared_task()
def clean_all_seats_if_no_bets_are_placed(round_id: str):
    game_round: dict = db.GameRound.find_one({"_id": ObjectId(round_id)})

    if game_round and game_round["start_timestamp"] is None:
        external_sio.emit("clean_seats", {}, room=game_round["game_id"])
        r.delete(f"{game_round['game_id']}:taken_seats")
        for seat_number in range(1, 14, 2):
            r.delete(f"{game_round['prev_round_id']}:{seat_number}")


@shared_task
def pay_winnings(game_id: str, game_round: dict):
    from apps.game.services.payment_manager import PaymentManager

    db.GameRound.find_one_and_update(
        {"_id": ObjectId(game_round["_id"])}, {"$set": {"show_dealer_cards": True}}
    )
    dealer_hand = Hand(game_round["dealer_cards"])

    external_sio.emit(
        "dealer_score",
        {"score": dealer_hand.get_score_repr(), "cards": game_round["dealer_cards"]},
        room=game_id,
    )
    taken_seats = {}
    db.GamePlayer.update_many(
        {"game_round": str(game_round["_id"])}, {"$set": {"archived": True}}
    )
    dealer_hand = Hand(game_round["dealer_cards"])
    merchants = db.Merchant.find(
        {"games.game_id": game_id},
        {"_id": 1, "win_url": 1, "schema_type": 1},
    )

    round_data = {
        "dealer_cards": game_round["dealer_cards"],
        "finished": game_round["finished"],
        "created_at": game_round["created_at"],
        "dealer_name": game_round["dealer_name"],
        "round_id": game_round["round_id"],
        "was_reset": game_round["was_reset"],
        "winner": game_round["winner"],
    }
    total_winnings = {}
    for merchant in merchants:
        win_url = merchant["win_url"]
        schema_type = merchant["schema_type"]
        game_players = db.GamePlayer.find(
            {
                "game_round": str(game_round["_id"]),
                "merchant": str(merchant["_id"]),
                "bet": {"$gt": 0},
            }
        )
        for game_player in game_players:
            game_player["_id"] = str(game_player["_id"])
            if game_player["seat_number"] % 2 == 1:
                taken_seats[game_player["seat_number"]] = {
                    "user_name": game_player["user_name"],
                    "cards": [],
                    "decision_time": None,
                    "last_action": None,
                    "making_decision": False,
                    "player_turn": False,
                    "score": "0",
                    "player_id": game_player["player_id"],
                    "insured": None,
                }
            win = PaymentManager.get_player_winning(game_player, dealer_hand)
            total_winnings[game_player["sid"]] = (
                total_winnings.get(game_player["sid"], 0) + win
            )
            if win > game_player["bet"]:
                send_winning_to_merchant_and_update_game_player.apply_async(
                    args=[game_player, win_url, win, round_data, schema_type],
                    max_retries=5,
                )
            elif win == game_player["bet"]:
                send_push_to_merchant_and_update_game_player.apply_async(
                    args=[game_player, win_url, win, round_data, schema_type],
                    max_retries=5,
                )
            else:
                send_lose_event_and_game_player_history.apply_async(
                    args=[game_player, win_url, round_data, schema_type],
                    max_retries=5,
                )
    for sid, win in total_winnings.items():
        external_sio.emit("total_winning", {"amount": win}, room=sid)
    r.set(f"{game_id}:taken_seats", json.dumps(taken_seats))
    start_new_round.apply_async(
        args=[game_id, str(game_round["_id"]), taken_seats], countdown=10, max_retries=5
    )
