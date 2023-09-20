import os
import pathlib
from typing import Union
from functools import lru_cache


class BaseConfig:
    BASE_DIR: pathlib.Path = pathlib.Path(__file__).parent

    SECRET_KEY: str = os.environ.get("SECRET_KEY", "3SFKXyF20Wz1Ys9wFmzD")

    ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS").split(" ")

    MONGODB_URL: str = os.environ.get("BLACKJACK_MONGODB_URL")

    CELERY_BROKER_URL: str = os.environ.get(
        "BLACKJACK_CELERY_BROKER_URL", "redis://127.0.0.1:6379/0"
    )
    CELERY_RESULT_BACKEND: str = os.environ.get(
        "BLACKJACK_CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/0"
    )
    WS_MESSAGE_QUEUE: str = os.environ.get(
        "BLACKJACK_WS_MESSAGE_QUEUE", "redis://127.0.0.1:6379/0"
    )
    REDIS_CACHE_URL: str = os.environ.get("REDIS_CACHE_URL", "redis://127.0.0.1:6379/0")
    REDIS_HOST_NAME: str = os.environ.get("REDIS_HOST_NAME")
    REDIS_CACHE_EXPIRATION_TIME = 1800

    PP_MULTIPLIER = 26
    CP_MULTIPLIER = 13
    MP_MULTIPLIER = 7

    ST_MULTIPLIER = 101
    SF_MULTIPLIER = 41
    TK_MULTIPLIER = 31
    S_MULTIPLIER = 11
    F_MULTIPLIER = 6

    MIN_SIDE_BET = 1
    MAX_SIDE_BET = 25


class DevelopmentConfig(BaseConfig):
    START_NEW_ROUND_SECONDS: int = 9
    ACCEPT_BETS_SECONDS: int = 16
    ACCEPT_INSURANCE_SECONDS: int = 7
    DATABASE_NAME: str = os.environ.get("DATABASE_NAME", "blackjack")
    TIME_FOR_REPEAT_CACHE: int = 7200


class ProductionConfig(BaseConfig):
    START_NEW_ROUND_SECONDS: int = 9
    ACCEPT_BETS_SECONDS: int = 16
    ACCEPT_INSURANCE_SECONDS: int = 7
    DATABASE_NAME: str = os.environ.get("DATABASE_NAME", "blackjack")
    TIME_FOR_REPEAT_CACHE: int = 7200


class TestingConfig(BaseConfig):
    START_NEW_ROUND_SECONDS: int = 9
    ACCEPT_BETS_SECONDS: int = 16
    ACCEPT_INSURANCE_SECONDS: int = 7
    DATABASE_NAME: str = "test_blackjack"
    TIME_FOR_REPEAT_CACHE: int = 7200


@lru_cache()
def get_settings() -> Union[ProductionConfig, TestingConfig, DevelopmentConfig]:
    config_cls_dict = {
        "development": DevelopmentConfig,
        "production": ProductionConfig,
        "testing": TestingConfig,
    }

    config_name = os.environ.get("ENVIRONMENT", "development")
    config_cls = config_cls_dict[config_name]
    return config_cls()


settings = get_settings()
