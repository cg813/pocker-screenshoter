from apps.game.services.utils import check_should_not_move_to_next_game_player


def test_game_player_is_active_and_made_action_after_refresh():
    game_player_before_refresh = {
        "is_active": True,
        "action_list": [{"bet": 1}, {"hit": 0}],
        "last_action": None,
        "finished_turn": False,
    }
    action_count = 1
    assert check_should_not_move_to_next_game_player(
        game_player_before_refresh, action_count
    )


def test_game_player_is_active_and_made_action_before_refresh():
    game_player_before_refresh = {
        "is_active": True,
        "action_list": [{"bet": 1}, {"hit": 0}],
        "last_action": None,
        "finished_turn": False,
    }
    action_count = 1
    assert check_should_not_move_to_next_game_player(
        game_player_before_refresh, action_count
    )


# TODO WRITE MORE TESTS
