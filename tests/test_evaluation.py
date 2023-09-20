from apps.game.services.evaluator import GameEvaluator


def get_evaluated_hand(player_cards, dealer_cards, bet_amount=0, user_balance=0):
    game_evaluator = GameEvaluator(player_cards, dealer_cards, bet_amount, user_balance)
    return game_evaluator.evaluate_hand()


def test_player_hand_6_with_two_cards():
    player_cards = ["2C", "4C"]
    dealer_cards = []

    evaluation = get_evaluated_hand(player_cards, dealer_cards)

    assert evaluation["values_str"] == "6"
    assert evaluation["bust"] is False
    assert evaluation["black_jack"] is False
    assert evaluation["is_21"] is False
    assert evaluation["actions"] == ["stand", "hit", "double"]


def test_player_hand_6_of_with_two_3s():
    player_cards = ["3C", "3D"]
    dealer_cards = []

    evaluation = get_evaluated_hand(player_cards, dealer_cards)

    assert evaluation["values_str"] == "6"
    assert evaluation["bust"] is False
    assert evaluation["black_jack"] is False
    assert evaluation["is_21"] is False
    assert evaluation["actions"] == ["stand", "split", "hit", "double"]


def test_player_hand_6_16_with_two_cards():
    player_cards = ["5C", "AC"]
    dealer_cards = []

    evaluation = get_evaluated_hand(player_cards, dealer_cards)
    assert evaluation["values_str"] == "6/16"
    assert evaluation["bust"] is False
    assert evaluation["black_jack"] is False
    assert evaluation["is_21"] is False
    assert evaluation["actions"] == ["stand", "hit", "double"]


def test_player_hand_21_with_two_cards():
    player_cards = ["JC", "AC"]
    dealer_cards = []

    evaluation = get_evaluated_hand(player_cards, dealer_cards)

    assert evaluation["values_str"] == "21"
    assert evaluation["bust"] is False
    assert evaluation["black_jack"] is True
    assert evaluation["is_21"] is True
    assert evaluation["actions"] == []


def test_player_hand_6_6_with_three_cards():
    player_cards = ["2S", "2C", "2D"]
    dealer_cards = []

    evaluation = get_evaluated_hand(player_cards, dealer_cards)

    assert evaluation["values_str"] == "6"
    assert evaluation["bust"] is False
    assert evaluation["black_jack"] is False
    assert evaluation["is_21"] is False
    assert evaluation["actions"] == ["stand", "hit"]


def test_player_hand_6_16_with_three_cards():
    player_cards = ["AS", "3C", "2D"]
    dealer_cards = []

    evaluation = get_evaluated_hand(player_cards, dealer_cards)

    assert evaluation["values_str"] == "6/16"
    assert evaluation["bust"] is False
    assert evaluation["black_jack"] is False
    assert evaluation["is_21"] is False
    assert evaluation["actions"] == ["stand", "hit"]


def test_player_hand_21_with_three_cards():
    player_cards = ["2S", "8C", "AD"]
    dealer_cards = []

    evaluation = get_evaluated_hand(player_cards, dealer_cards)
    assert evaluation["values_str"] == "21"
    assert evaluation["bust"] is False
    assert evaluation["black_jack"] is False
    assert evaluation["is_21"] is True
    assert evaluation["actions"] == []


def test_player_insurance_hand_6():
    player_cards = ["3S", "3C"]
    dealer_cards = ["AH"]

    evaluation = get_evaluated_hand(player_cards, dealer_cards)
    assert evaluation["values_str"] == "6"
    assert evaluation["bust"] is False
    assert evaluation["black_jack"] is False
    assert evaluation["is_21"] is False
    assert evaluation["actions"] == ["stand", "split", "hit", "double", "insurance"]


def test_player_insurance_hand_6_16():
    player_cards = ["5S", "AC"]
    dealer_cards = ["AH"]

    evaluation = get_evaluated_hand(player_cards, dealer_cards)
    assert evaluation["values_str"] == "6/16"
    assert evaluation["bust"] is False
    assert evaluation["black_jack"] is False
    assert evaluation["is_21"] is False
    assert evaluation["actions"] == ["stand", "hit", "double", "insurance"]


def test_player_insurance_hand_21():
    player_cards = ["TC", "AD"]
    dealer_cards = ["AH"]

    evaluation = get_evaluated_hand(player_cards, dealer_cards)
    assert evaluation["values_str"] == "21"
    assert evaluation["bust"] is False
    assert evaluation["black_jack"] is True
    assert evaluation["is_21"] is True
    assert evaluation["actions"] == []


def test_player_busted():
    player_cards = ["2S", "TC", "TD"]
    dealer_cards = ["AH"]

    evaluation = get_evaluated_hand(player_cards, dealer_cards)
    assert evaluation["values_str"] == "22"
    assert evaluation["bust"] is True
    assert evaluation["black_jack"] is False
    assert evaluation["is_21"] is False
    assert evaluation["actions"] == []


def test_player_bust_three_tens():
    player_cards = ["TS", "TC", "TD"]
    dealer_cards = ["AH"]

    evaluation = get_evaluated_hand(player_cards, dealer_cards)
    assert evaluation["values_str"] == "30"
    assert evaluation["bust"] is True
    assert evaluation["black_jack"] is False
    assert evaluation["is_21"] is False
    assert evaluation["actions"] == []


def test_player_two_aces():
    player_cards = ["AS", "AC"]
    dealer_cards = ["AH"]

    evaluation = get_evaluated_hand(player_cards, dealer_cards)
    assert evaluation["values_str"] == "2/12"
    assert evaluation["bust"] is False
    assert evaluation["black_jack"] is False
    assert evaluation["is_21"] is False
    assert evaluation["actions"] == ["stand", "split", "hit", "double", "insurance"]


def test_player_two_8_one_ace():
    player_cards = ["AS", "8C", "8H"]
    dealer_cards = ["AH"]

    evaluation = get_evaluated_hand(player_cards, dealer_cards)
    assert evaluation["values_str"] == "17"
    assert evaluation["bust"] is False
    assert evaluation["black_jack"] is False
    assert evaluation["is_21"] is False
    assert evaluation["actions"] == ["stand", "hit"]


def test_player_three_7():
    player_cards = ["7S", "7C", "7H"]
    dealer_cards = ["AH"]

    evaluation = get_evaluated_hand(player_cards, dealer_cards)
    assert evaluation["values_str"] == "21"
    assert evaluation["bust"] is False
    assert evaluation["black_jack"] is False
    assert evaluation["is_21"] is True
    assert evaluation["actions"] == []


def test_player_three_8():
    player_cards = ["8S", "8C", "8H"]
    dealer_cards = ["AH"]

    evaluation = get_evaluated_hand(player_cards, dealer_cards)
    assert evaluation["values_str"] == "24"
    assert evaluation["bust"] is True
    assert evaluation["black_jack"] is False
    assert evaluation["is_21"] is False
    assert evaluation["actions"] == []


def test_actions_for_double_with_insufficient_balance():
    player_cards = ["3C", "4C"]
    dealer_cards = []
    bet = 20
    balance = 19

    evaluation = get_evaluated_hand(player_cards, dealer_cards, bet, balance)

    assert evaluation["values_str"] == "7"
    assert evaluation["bust"] is False
    assert evaluation["black_jack"] is False
    assert evaluation["is_21"] is False
    assert evaluation["actions"] == ["stand", "hit"]


def test_actions_for_double_and_split_with_insufficient_balance():
    player_cards = ["8C", "8H"]
    dealer_cards = []
    bet = 20
    balance = 8

    evaluation = get_evaluated_hand(player_cards, dealer_cards, bet, balance)

    assert evaluation["values_str"] == "16"
    assert evaluation["bust"] is False
    assert evaluation["black_jack"] is False
    assert evaluation["is_21"] is False
    assert evaluation["actions"] == ["stand", "hit"]


def test_actions_for_insurance_with_insufficient_balance():
    player_cards = ["8C", "8H"]
    dealer_cards = ["AH"]
    bet = 20
    balance = 9

    evaluation = get_evaluated_hand(player_cards, dealer_cards, bet, balance)

    assert evaluation["values_str"] == "16"
    assert evaluation["bust"] is False
    assert evaluation["black_jack"] is False
    assert evaluation["is_21"] is False
    assert evaluation["actions"] == ["stand", "hit"]
