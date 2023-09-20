from typing import List, Optional

from bson import ObjectId
from pydantic import AnyHttpUrl, BaseModel, Field


class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid object id")
        return ObjectId(v)

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")


class GameBaseModel(BaseModel):
    name: str
    table_stream_key_1: str
    table_stream_key_2: str


class GameResponseModel(GameBaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class GameUpdateModel(BaseModel):
    name: str
    game_status: bool = True
    is_break: bool = False
    table_stream_key_1: str
    table_stream_key_2: str
    type: str


class GameMerchantModel(BaseModel):
    game_id: str
    game_name: str
    min_bet: float
    max_bet: float
    bet_range: List[float]
    decision_make_time: int = 15

    is_active: bool


class MerchantBackOfficeModel(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    name: str

    games: Optional[List[GameMerchantModel]]
    validate_token_url: AnyHttpUrl
    transaction_url: AnyHttpUrl

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class BetModel(BaseModel):
    amount: int
    bet_type: str
