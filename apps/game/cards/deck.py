from typing import NamedTuple, Dict


class Card(NamedTuple):
    suit: str
    score: int

    def __lt__(self, other: "Card"):
        return self.score <= other.score


def get_deck() -> Dict[str, Card]:
    suits = ["S", "C", "D", "H"]
    cards = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K"]
    scores = {
        "A": 11,
        "2": 2,
        "3": 3,
        "4": 4,
        "5": 5,
        "6": 6,
        "7": 7,
        "8": 8,
        "9": 9,
        "T": 10,
        "J": 10,
        "Q": 10,
        "K": 10,
    }
    card_deck = {}
    for deck_number in range(1, 7):
        for suit in suits:
            for card in cards:
                card_deck[str(deck_number) + card + suit] = Card(suit, scores[card])
    return card_deck


deck = get_deck()
