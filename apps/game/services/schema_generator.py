import inflection

from apps.game.documents import GamePlayer


def generate_authentication_request_data(launch_token: str, schema_type: str):
    data = {"launch_token": launch_token, "request_scope": "country"}
    inflector = get_request_inflector(schema_type)
    return inflector(data)


def inflect_response_data(data: dict):
    new_data = dict()
    for key, value in data.items():
        snake_key = inflection.underscore(key)
        new_data[snake_key] = value
    return new_data


def generate_get_balance_request_data(schema_type: str, game_player: GamePlayer):
    data = {"token": game_player["user_token"], "currency": "USD", "hash": ""}
    inflector = get_request_inflector(schema_type)
    return inflector(data)


def generate_bet_request_data(
    schema_type: str, amount: float, game_player: dict, external_id: str
) -> dict:
    data = {
        "token": game_player["user_token"],
        "amount": amount,
        "currency": "USD",
        "game_id": game_player["game_id"],
        "round_id": game_player["game_round"],
        "external_id": external_id,
        "hash": "",
        "transaction_type": "bet",
    }
    inflector = get_request_inflector(schema_type)
    return inflector(data)


def generate_win_request_data(
    schema_type: str, amount: float, game_player: GamePlayer, external_id: str
) -> dict:
    data = {
        "token": game_player["user_token"],
        "amount": amount,
        "currency": "USD",
        "game_id": game_player["game_id"],
        "round_id": game_player["game_round"],
        "external_id": external_id,
        "bet_external_id": game_player["external_ids"].get("bet"),
        "hash": "",
        "transaction_type": "win",
    }
    inflector = get_request_inflector(schema_type)
    return inflector(data)


def generate_reset_request_data(
    schema_type: str, amount: float, game_player: GamePlayer, bet_type: str
) -> dict:
    data = {
        "token": game_player["user_token"],
        "amount": amount,
        "currency": "USD",
        "game_id": game_player["game_id"],
        "round_id": game_player["game_round"],
        "external_id": game_player["external_ids"][f"cancel_{bet_type}"],
        "canceled_external_id": game_player["external_ids"][bet_type],
        "hash": "",
        "transaction_type": "rollback",
    }
    inflector = get_request_inflector(schema_type)
    return inflector(data)


def generate_tip_request_data(
    schema_type: str,
    amount: float,
    user_token: str,
    external_id: str,
    game_id: str,
    round_id: str,
) -> dict:
    data = {
        "token": user_token,
        "amount": amount,
        "currency": "USD",
        "game_id": game_id,
        "round_id": round_id,
        "external_id": external_id,
        "hash": "",
        "transaction_type": "bet",
    }
    inflector = get_request_inflector(schema_type)
    return inflector(data)


def get_request_inflector(schema_type):
    return {
        "camel": inflect_from_snake_to_camel_case,
        "capital_camel": inflect_from_snake_to_capital_came_case,
        "snake": lambda data: data,
    }.get(schema_type)


def inflect_from_camel_to_snake_case(data: dict) -> dict:
    new_data = dict()
    for camel_key, value in data.items():
        snake_key = inflection.underscore(camel_key)
        new_data[snake_key] = value
    return new_data


def inflect_from_snake_to_capital_came_case(data: dict) -> dict:
    new_data = dict()
    for snake_key, value in data.items():
        camel_key = inflection.camelize(snake_key)
        new_data[camel_key] = value
    return new_data


def inflect_from_snake_to_camel_case(data: dict) -> dict:
    new_data = dict()
    for snake_key, value in data.items():
        camel_key = inflection.camelize(snake_key)
        camel_key = camel_key[0].lower() + camel_key[1:]
        new_data[camel_key] = value
    return new_data
