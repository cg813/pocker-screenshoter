from typing import List, Optional

from typing import Literal
from beanie import Document
from pydantic import AnyHttpUrl, Field

from .models import GameMerchantModel
from .services.utils import generate_api_key, get_timestamp


class Merchant(Document):
    name: str
    api_key: Optional[str] = generate_api_key()

    games: Optional[List[GameMerchantModel]]

    transaction_url: AnyHttpUrl
    validate_token_url: AnyHttpUrl
    bet_url: AnyHttpUrl
    win_url: AnyHttpUrl
    rollback_url: AnyHttpUrl
    get_balance_url: AnyHttpUrl

    schema_type: Literal["camel", "capital_camel", "snake"]


class Game(Document):
    created_at: str = Field(default_factory=get_timestamp)
    updated_at: str = Field(default_factory=get_timestamp)

    name: str
    type: Literal["european", "american"] = "european"
    game_status: bool

    is_break: bool = False
    is_open: bool = False

    table_stream_key_1: str
    table_stream_key_2: str


class GameRound(Document):

    created_at: str = Field(default_factory=get_timestamp)
    updated_at: str = Field(default_factory=get_timestamp)

    card_count: int = 0

    game_id: str
    round_id: str

    dealer_cards: Optional[List] = []

    start_timestamp: str = None
    insurance_timestamp: str = None
    finished_dealing: bool = False
    show_dealer_cards: bool = False

    winner: str = None
    was_reset: bool = False
    finished: bool = False
    prev_round_id: str = None

    dealer_name: str = None


class GamePlayer(Document):

    join_game_at: str = get_timestamp()
    updated_at: str = get_timestamp()
    left_game_at: str = None

    sid: str

    user_token: str
    user_id: str
    user_name: str

    decision_time: str
    making_decision: bool = False
    player_turn: bool = False
    finished_turn: bool = False

    game_id: str
    game_round: str
    merchant: str
    seat_number: int = None
    action_list: List = []
    last_action: str = None
    cards: List = []
    player_id: str = None
    insured: Optional[bool] = None

    bet: float = 0
    bet_list: Optional[List] = []
    bet_21_3: float = 0
    bet_21_3_list: Optional[List] = []
    bet_21_3_winning: float = 0
    bet_21_3_combination: str = None
    bet_perfect_pair: float = 0
    bet_perfect_pair_list: Optional[List] = []
    bet_perfect_pair_winning: float = 0
    bet_perfect_pair_combination: str = None

    deposit: float
    winning_amount: float = 0
    total_bet: float = 0
    prev_winning_amount: float = None
    archived_game_player_id: str = None
    archived: bool = False
    is_reset: bool = False
    rejected: bool = False
    detail: str = None
    is_active: bool = True

    external_ids: dict = {}
    inactivity_check_time: int = 0
    #
    # is_dealer: bool
    # is_active: bool = True


class Tip(Document):
    created_at: str = Field(default_factory=get_timestamp)
    user_id: str
    merchant_id: str
    game_id: str
    round_id: str
    amount: float
    username: str

    external_id: str


class Break(Document):

    number: int
    name: str
    text: str
