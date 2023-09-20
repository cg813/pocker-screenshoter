from apps.game.cards.hand import Hand


def test_hand_with_ac_7d():
    hand = Hand(["1AC", "17D"])
    h = hand._hand_scores
    assert hand.score == 18
    assert h.score == 18
    assert h.second_score == 8
    score_str = hand.get_score_repr()
    assert score_str == "18/8"


def test_hand_with_ac_2d_4h():
    hand = Hand(["1AC", "12D", "14H"])
    h = hand._hand_scores
    assert hand.score == 17
    assert h.score == 17
    assert h.second_score == 7
    score_str = hand.get_score_repr()
    assert score_str == "17/7"


def test_hand_with_ac_6d_ad():
    hand = Hand(["1AC", "16D", "1AD"])
    h = hand._hand_scores
    assert hand.score == 18
    assert h.score == 18
    assert h.second_score == 8
    score_str = hand.get_score_repr()
    assert score_str == "18/8"


def test_hand_with_ac_6d_ad_10s_5d():
    hand = Hand(["1AC", "16D", "1AD", "1TS", "15D"])
    h = hand._hand_scores
    assert hand.score == 23
    assert h.score == 23
    assert h.second_score == 23
    score_str = hand.get_score_repr()
    assert score_str == "23"


def test_hand_with_2c_3d_4d():
    hand = Hand(["12C", "13D", "14D"])
    h = hand._hand_scores
    assert hand.score == 9
    assert h.score == 9
    assert h.second_score == 9
    score_str = hand.get_score_repr()
    assert score_str == "9"


def test_hand_with_ac_ad_9d():
    hand = Hand(["1AC", "1AD", "19D"])
    h = hand._hand_scores
    assert hand.score == 21
    assert h.score == 21
    assert h.second_score == 11
    score_str = hand.get_score_repr()
    assert score_str == "21"


def test_possible_actions():
    hand = Hand(["1AC", "1AD"])
    actions = hand.get_possible_player_actions()
    assert actions == ["stand", "hit", "double", "split"]


def test_possible_actions_with_21():
    hand = Hand(["1AC", "1JH"])
    actions = hand.get_possible_player_actions()
    assert hand.score == 21
    assert actions == []


def test_two_aces():
    hand = Hand(["2AC", "2AD", "2TD"])
    assert hand.score == 12


def test_hand_with_2c_3d_ah_with_double_action():
    hand = Hand(["12C", "13D", "1AD"], last_action="double")
    score_str = hand.get_score_repr()
    assert score_str == "16"


def test_hand_with_ac_5d_with_split_action():
    hand = Hand(["1AC", "15D"], last_action="split:1")
    score_str = hand.get_score_repr()
    assert score_str == "16"
