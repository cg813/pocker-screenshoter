from apps.game.cards.hand import Hand
from apps.game.services.payment_manager import PaymentManager


game_player = {"cards": [], "insured": False, "bet": 0}


def test_player_bj_dealer_bj_with_insurance():
    game_player["cards"] = ["1AC", "1TC"]
    game_player["insured"] = True
    game_player["bet"] = 10
    game_player["last_action"] = None
    game_player["bet_21_3_winning"] = 0
    game_player["bet_perfect_pair_winning"] = 0
    dealer_hand = Hand(["1AH", "1TH"])
    total_winning = PaymentManager.get_player_winning(game_player, dealer_hand)

    assert total_winning == game_player["bet"]


def test_player_bj_dealer_bj_no_insurance():
    game_player["cards"] = ["1AC", "1TC"]
    game_player["insured"] = False
    game_player["bet"] = 10
    game_player["last_action"] = None
    game_player["bet_21_3_winning"] = 0
    game_player["bet_perfect_pair_winning"] = 0
    dealer_hand = Hand(["1AH", "1TH"])
    total_winning = PaymentManager.get_player_winning(game_player, dealer_hand)

    assert total_winning == game_player["bet"]


def test_player_bj_dealer_no_bj_with_insurance():
    game_player["cards"] = ["1AC", "1TC"]
    game_player["insured"] = True
    game_player["bet"] = 10
    game_player["last_action"] = None
    game_player["bet_21_3_winning"] = 0
    game_player["bet_perfect_pair_winning"] = 0
    dealer_hand = Hand(["1AH", "19H"])
    total_winning = PaymentManager.get_player_winning(game_player, dealer_hand)

    assert total_winning == game_player["bet"] * 2.5


def test_player_bj_dealer_no_bj_no_insurance():
    game_player["cards"] = ["1AC", "1TC"]
    game_player["insured"] = False
    game_player["bet"] = 10
    game_player["last_action"] = None
    game_player["bet_21_3_winning"] = 0
    game_player["bet_perfect_pair_winning"] = 0
    dealer_hand = Hand(["1AH", "19H"])
    total_winning = PaymentManager.get_player_winning(game_player, dealer_hand)

    assert total_winning == game_player["bet"] * 2.5


def test_player_20_dealer_bj_with_insurance():
    game_player["cards"] = ["1AC", "19C"]
    game_player["insured"] = True
    game_player["bet"] = 10
    game_player["last_action"] = None
    game_player["bet_21_3_winning"] = 0
    game_player["bet_perfect_pair_winning"] = 0
    dealer_hand = Hand(["1AH", "1TH"])
    total_winning = PaymentManager.get_player_winning(game_player, dealer_hand)

    assert total_winning == game_player["bet"] * 1.5


def test_player_21_dealer_bj_with_insurance():
    game_player["cards"] = ["1AC", "18C", "12C"]
    game_player["insured"] = True
    game_player["bet"] = 10
    game_player["last_action"] = None
    game_player["bet_21_3_winning"] = 0
    game_player["bet_perfect_pair_winning"] = 0
    dealer_hand = Hand(["1AH", "1TH"])
    total_winning = PaymentManager.get_player_winning(game_player, dealer_hand)

    assert total_winning == game_player["bet"] * 1.5


def test_player_20_dealer_bj_no_insurance():
    game_player["cards"] = ["1AC", "19C"]
    game_player["insured"] = False
    game_player["bet"] = 10
    game_player["last_action"] = None
    game_player["bet_21_3_winning"] = 0
    game_player["bet_perfect_pair_winning"] = 0
    dealer_hand = Hand(["1AH", "1TH"])
    total_winning = PaymentManager.get_player_winning(game_player, dealer_hand)

    assert total_winning == 0


def test_player_21_dealer_20_with_insurance():
    game_player["cards"] = ["1AC", "18C", "12C"]
    game_player["insured"] = True
    game_player["bet"] = 10
    game_player["last_action"] = None
    game_player["bet_21_3_winning"] = 0
    game_player["bet_perfect_pair_winning"] = 0
    dealer_hand = Hand(["1AH", "19H"])
    total_winning = PaymentManager.get_player_winning(game_player, dealer_hand)

    assert total_winning == game_player["bet"] * 2


def test_player_21_dealer_20_no_insurance():
    game_player["cards"] = ["1AC", "18C", "12C"]
    game_player["insured"] = False
    game_player["bet"] = 10
    game_player["last_action"] = None
    game_player["bet_21_3_winning"] = 0
    game_player["bet_perfect_pair_winning"] = 0
    dealer_hand = Hand(["1AH", "19H"])
    total_winning = PaymentManager.get_player_winning(game_player, dealer_hand)

    assert total_winning == game_player["bet"] * 2


def test_player_21_dealer_21_with_insurance():
    game_player["cards"] = ["1AC", "18C", "12C"]
    game_player["insured"] = True
    game_player["bet"] = 10
    game_player["last_action"] = None
    game_player["bet_21_3_winning"] = 0
    game_player["bet_perfect_pair_winning"] = 0
    dealer_hand = Hand(["1AH", "18H", "12H"])
    total_winning = PaymentManager.get_player_winning(game_player, dealer_hand)

    assert total_winning == game_player["bet"]


def test_player_21_dealer_21_no_insurance():
    game_player["cards"] = ["1AC", "18C", "12C"]
    game_player["insured"] = False
    game_player["bet"] = 10
    game_player["last_action"] = None
    game_player["bet_21_3_winning"] = 0
    game_player["bet_perfect_pair_winning"] = 0
    dealer_hand = Hand(["1AH", "18H", "12H"])
    total_winning = PaymentManager.get_player_winning(game_player, dealer_hand)

    assert total_winning == game_player["bet"]


def test_player_21_dealer_bust_with_insurance():
    game_player["cards"] = ["1AC", "18C", "12C"]
    game_player["insured"] = True
    game_player["bet"] = 10
    game_player["last_action"] = None
    game_player["bet_21_3_winning"] = 0
    game_player["bet_perfect_pair_winning"] = 0
    dealer_hand = Hand(["1AH", "18H", "14H"])
    total_winning = PaymentManager.get_player_winning(game_player, dealer_hand)

    assert total_winning == game_player["bet"] * 2


def test_player_21_dealer_bust_no_insurance():
    game_player["cards"] = ["1AC", "18C", "12C"]
    game_player["insured"] = False
    game_player["bet"] = 10
    game_player["last_action"] = None
    game_player["bet_21_3_winning"] = 0
    game_player["bet_perfect_pair_winning"] = 0
    dealer_hand = Hand(["1AH", "18H", "14H"])
    total_winning = PaymentManager.get_player_winning(game_player, dealer_hand)

    assert total_winning == game_player["bet"] * 2


def test_player_bust_dealer_bj_with_insurance():
    game_player["cards"] = ["1TC", "18C", "15C"]
    game_player["insured"] = True
    game_player["bet"] = 10
    game_player["last_action"] = None
    game_player["bet_21_3_winning"] = 0
    game_player["bet_perfect_pair_winning"] = 0
    dealer_hand = Hand(["1AH", "1TH"])
    total_winning = PaymentManager.get_player_winning(game_player, dealer_hand)

    assert total_winning == game_player["bet"] * 1.5


def test_player_bust_dealer_bj_no_insurance():
    game_player["cards"] = ["1TC", "18C", "15C"]
    game_player["insured"] = False
    game_player["bet"] = 10
    game_player["last_action"] = None
    game_player["bet_21_3_winning"] = 0
    game_player["bet_perfect_pair_winning"] = 0
    dealer_hand = Hand(["1AH", "1TH"])
    total_winning = PaymentManager.get_player_winning(game_player, dealer_hand)

    assert total_winning == 0


def test_player_bust_dealer_21_with_insurance():
    game_player["cards"] = ["1TC", "18C", "15C"]
    game_player["insured"] = True
    game_player["bet"] = 10
    game_player["last_action"] = None
    game_player["bet_21_3_winning"] = 0
    game_player["bet_perfect_pair_winning"] = 0
    dealer_hand = Hand(["1AH", "18H", "12H"])
    total_winning = PaymentManager.get_player_winning(game_player, dealer_hand)

    assert total_winning == 0


def test_player_bust_dealer_21_no_insurance():
    game_player["cards"] = ["1TC", "18C", "15C"]
    game_player["insured"] = False
    game_player["bet"] = 10
    game_player["last_action"] = None
    game_player["bet_21_3_winning"] = 0
    game_player["bet_perfect_pair_winning"] = 0
    dealer_hand = Hand(["1AH", "18H", "12H"])
    total_winning = PaymentManager.get_player_winning(game_player, dealer_hand)

    assert total_winning == 0


def test_player_bust_dealer_bust_with_insurance():
    game_player["cards"] = ["1TC", "18C", "15C"]
    game_player["insured"] = True
    game_player["bet"] = 10
    game_player["last_action"] = None
    game_player["bet_21_3_winning"] = 0
    game_player["bet_perfect_pair_winning"] = 0
    dealer_hand = Hand(["1AH", "18H", "15H"])
    total_winning = PaymentManager.get_player_winning(game_player, dealer_hand)

    assert total_winning == 0


def test_player_bust_dealer_bust_no_insurance():
    game_player["cards"] = ["1TC", "18C", "15C"]
    game_player["insured"] = False
    game_player["bet"] = 10
    game_player["last_action"] = None
    game_player["bet_21_3_winning"] = 0
    game_player["bet_perfect_pair_winning"] = 0
    dealer_hand = Hand(["1AH", "18H", "15H"])
    total_winning = PaymentManager.get_player_winning(game_player, dealer_hand)

    assert total_winning == 0
