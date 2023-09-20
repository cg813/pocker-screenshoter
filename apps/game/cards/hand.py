from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

from apps.game.cards.deck import Card, deck


@dataclass
class HandScores:
    score: int
    second_score: int


class Hand:
    def __init__(self, cards: List[str], last_action: str = None):
        self.cards_list: List[str] = cards
        self._cards: List[Card] = [deck[card] for card in cards]
        self.str_card: List[str] = cards
        self.possible_actions: List[str] = []
        self._hand_scores = self.get_hand_scores()
        self._score = self.get_score()
        self.last_action = last_action

    @property
    def cards(self) -> List[Card]:
        return self._cards

    @property
    def str_cards(self) -> List[str]:
        return self.str_card

    @property
    def score(self) -> int:
        return self._score

    def get_hand_scores(self) -> HandScores:
        hand_scores = HandScores(0, 0)
        self.cards.sort()
        for card in self.cards:
            if card.score == 11 and hand_scores.score + card.score < 21:
                hand_scores.second_score += 1
                hand_scores.score += card.score
                continue
            elif card.score == 11 and hand_scores.score + card.score == 21:
                hand_scores.second_score += 1
                hand_scores.score += card.score
                continue
            elif card.score == 11 and hand_scores.score + card.score > 21:
                hand_scores.score += 1
                hand_scores.second_score += 1
                continue
            hand_scores.score += card.score
            hand_scores.second_score += card.score
        return hand_scores

    def get_score(self) -> int:
        if self._hand_scores.score <= 21:
            return self._hand_scores.score
        return self._hand_scores.second_score

    def get_score_repr(self) -> str:
        hard_score, soft_score = self._hand_scores.score, self._hand_scores.second_score
        if hard_score == 21 and len(self.cards) == 2:
            if self.last_action in ["split:1", "split:2"]:
                return "21"
            return "BJ"
        if hard_score == 21:
            return str(hard_score)
        if hard_score > 21:
            return str(soft_score)
        if hard_score < 21:
            if self.last_action == "double":
                return str(hard_score)
            if self.last_action in ["split:1", "split:2"] and "A" in self.cards_list[0]:
                return str(hard_score)
            if hard_score != soft_score:
                return f"{hard_score}/{soft_score}"
            return str(hard_score)

    def get_possible_player_actions(self) -> List[str]:
        if self.check_stand_action():
            self.possible_actions.append("stand")
        if self.check_hit_action():
            self.possible_actions.append("hit")
        if self.check_double():
            self.possible_actions.append("double")
        if self.check_split_action():
            self.possible_actions.append("split")
        return self.possible_actions

    def can_continue_game(self) -> bool:
        if self.score >= 21:
            return False
        elif (
            self.last_action and "split" in self.last_action
        ) and "A" in self.str_card[0]:
            return False
        return True

    def check_split_action(self) -> bool:
        if len(self.cards) == 2 and self.cards[0].score == self.cards[1].score:
            if self.last_action not in ["split:1", "split:2"]:
                return True
        return False

    def check_hit_action(self) -> bool:
        if self.score < 21:
            return True
        return False

    def check_double(self) -> bool:
        if len(self.cards) == 2 and self.score < 21:
            return True
        return False

    def dealer_action(self) -> bool:
        if self.score < 17:
            return True
        return False

    def check_stand_action(self) -> bool:
        if self.score < 21:
            return True
        return False

    @staticmethod
    def generate_data(
        cards: List[str], last_action: str = None
    ) -> Tuple[Dict[str, Any], "Hand"]:
        hand = Hand(cards, last_action)
        return {
            "score": hand.score,
            "actions": hand.get_possible_player_actions(),
            "cards": hand.str_cards,
        }, hand
