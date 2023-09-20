rank_values = {
    "A": [1, 11],
    "K": [10, 10],
    "Q": [10, 10],
    "J": [10, 10],
    "T": [10, 10],
    "9": [9, 9],
    "8": [8, 8],
    "7": [7, 7],
    "6": [6, 6],
    "5": [5, 5],
    "4": [4, 4],
    "3": [3, 3],
    "2": [2, 2],
}


class GameEvaluator:
    """
    CUSTOM GAME EVALUATION
    :method evaluate hand - returns a dictionary of evaluated hand, keys are following:
        :key cards - is a list representation of player cards
        :key values - is a list representation of two possible value of a hand
        :key values_str - is a string representation of one/two possible values of hand
        :key bust - is a boolean representation of whether the hand is busted or not
        :key black_jack - is a boolean representation of whether hand is a black-jack or not
        :key is_21 - is a boolean representation of whether the hand is 21 or not
        :key actions - is a lost representation of possible actions for player to proceed
    """

    def __init__(
        self, player_cards: list, dealer_cards=[], bet_amount=0, user_balance=0
    ):
        """
        :param player_cards - is a list representation of player cards
        :dealer_card - is a list representation of dealer's cards by default it is empty
        """
        self.cards = player_cards
        self.dealer_cards = dealer_cards

        self.bet_amount = bet_amount
        self.user_balance = user_balance

        self.ranks = list()
        self.rank_values = list()
        self.values = None
        self.values_str = None

        self.bust = False
        self.black_jack = False
        self.is_21 = False

        self.possible_actions = list()

    def evaluate_hand(self):
        self.get_total_values()
        self.evaluate_state()

        if not self.bust and not self.is_21 and len(self.cards) > 1:
            self.possible_actions.append("stand")
            self.check_for_split()
            self.check_for_hit()
            self.check_for_double()

        if len(self.cards) == 2 and not self.black_jack:
            self.check_for_insurance()

        return self.generate_evaluation()

    def get_str_value_of_hand(self):
        self.get_total_values()
        return self.generate_evaluation()

    def get_total_values(self):
        for card in self.cards:
            self.ranks.append(card[0])
        for rank in self.ranks:
            self.rank_values.append(rank_values[rank])

        if self.ranks == ["A", "A"]:
            self.values = [2, 12]
        else:
            self.values = list(map(sum, zip(*self.rank_values)))

        self.values_str = self.generate_value_string_representation()

    def evaluate_state(self):
        if all(value > 21 for value in self.values):
            self.bust = True

        if any(value == 21 for value in self.values):
            if len(self.cards) == 2:
                self.black_jack = True
            self.is_21 = True

    def check_for_double(self):
        if len(self.cards) == 2 and all(value < 21 for value in self.values):
            if self.check_balance():
                self.possible_actions.append("double")

    def check_for_split(self):
        if len(self.cards) == 2 and self.ranks[0] == self.ranks[1]:
            if self.check_balance():
                self.possible_actions.append("split")

    def check_for_hit(self):
        for value in self.values:
            if value < 21 and "hit" not in self.possible_actions:
                self.possible_actions.append("hit")

    def check_for_insurance(self):
        if (
            len(self.dealer_cards) == 1
            and "A" in self.dealer_cards[0]
            and len(self.cards) == 2
        ):
            if self.check_balance_for_insurance():
                self.possible_actions.append("insurance")

    def check_balance(self):
        if float(self.user_balance) < float(self.bet_amount):
            return False
        return True

    def check_balance_for_insurance(self):
        if float(self.user_balance) < float(self.bet_amount) / 2:
            return False
        return True

    def generate_value_string_representation(self):
        if len(set(self.values)) == 1:
            return str(self.values[0])
        elif any(value == 21 for value in self.values):
            return "21"
        elif any(value > 21 for value in self.values):
            return str(sorted(self.values)[0])
        return f"{self.values[0]}/{self.values[1]}"

    @staticmethod
    def can_continue_game(cards: list):
        cards_sum = 0
        for card in cards:
            cards_sum += rank_values.get(card[0])[0]
        if cards_sum >= 21:
            return False
        return True

    def generate_evaluation(self):
        return {
            "cards": self.cards,
            "values": self.values,
            "values_str": self.values_str,
            "bust": self.bust,
            "black_jack": self.black_jack,
            "is_21": self.is_21,
            "actions": self.possible_actions,
        }
