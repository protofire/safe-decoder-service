"""
Base settings file for FastApi application.
"""

import logging.config
import os
import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.loggers.safe_logger import SafeJsonFormatter


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.environ.get("ENV_FILE", ".env"),
        env_file_encoding="utf-8",
        extra="allow",
        case_sensitive=True,
    )
    TEST: bool = False
    LOG_LEVEL: str = "INFO"
    LOG_LEVEL_EVENTS_SERVICE: str = "INFO"
    REDIS_URL: str = "redis://"
    DATABASE_URL: str = "psql://postgres:"
    DATABASE_POOL_CLASS: str = "AsyncAdaptedQueuePool"
    DATABASE_POOL_SIZE: int = 10
    RABBITMQ_AMQP_URL: str = "amqp://guest:guest@"
    RABBITMQ_AMQP_EXCHANGE: str = "safe-transaction-service-events"
    RABBITMQ_DECODER_EVENTS_QUEUE_NAME: str = "safe-decoder-service"
    SECRET_KEY: str = secrets.token_urlsafe(
        32
    )  # In production it must be defined so it doesn't change
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin"
    ADMIN_TOKEN_EXPIRATION_SECONDS: int = (
        7 * 24 * 60 * 60
    )  # Admin token expires in 1 week
    ETHERSCAN_API_KEY: str = ""
    ETHERSCAN_MAX_REQUESTS: int = 1
    BLOCKSCOUT_MAX_REQUESTS: int = 1
    SOURCIFY_MAX_REQUESTS: int = 100
    CONTRACT_MAX_DOWNLOAD_RETRIES: int = (
        90  # Task running once per day, means 3 months trying.
    )
    CONTRACT_LOGO_BASE_URL: str = (
        "https://safe-transaction-assets.safe.global/contracts/logos"
    )
    CONTRACTS_TRUSTED_FOR_DELEGATE_CALL: list[str] = [
        "MultiSendCallOnly",
        "SignMessageLib",
        "SafeMigration",
    ]
    # Chains where Safe contracts are not deployed on the canonical addresses.
    # chain_id -> contract_name -> addresses
    SAFE_DEPLOYMENTS_OVERRIDES: dict[int, dict[str, list[str]]] = {
        728126428: {  # TRON Mainnet
            "Safe": ["0x1619de3c122b610ef788a1bc13772a0c8506ed09"],
            "SafeL2": ["0x5c03b2637513d2ee57603d8aef67f6989b426c14"],
            "SafeProxyFactory": ["0x39235a65aed90f13a2bbec5c53f0d710cdbbc5d7"],
            "MultiSend": ["0x92f65c8f5eeb25617acf7f3626936b5ab0c63680"],
            "MultiSendCallOnly": ["0x6a8824d50b7aeec29a6ec61ce928d964331ab35f"],
            "CompatibilityFallbackHandler": [
                "0x3f70526ed0567473d3ce222e3aae634baa932c8e"
            ],
            "SignMessageLib": ["0x3711ba027fd46d537e17b2b12231818b4df89f14"],
            "SimulateTxAccessor": ["0xb7b37186a996b2e6371397a6056fdd34ef33ad92"],
        },
        2494104990: {  # TRON Shasta
            "Safe": ["0x48a430a9e259b1fa41408cef6103c56d8051ef36"],
            "SafeL2": ["0x1bdf92b7ad0aa881e811c540bde8600c3e2a41c8"],
            "SafeProxyFactory": ["0xe010048abee39457ddaa556ed782732ca80ab39c"],
            "MultiSend": ["0x165a462e2017d8bf5e156e6d1ca6ac807023f861"],
            "MultiSendCallOnly": ["0xf22794c67fe86468272a25401fe95acb6df39f19"],
            "CompatibilityFallbackHandler": [
                "0x2c8c449ae05a7d43b9ebe1bd49600630d11c3ab5"
            ],
            "SignMessageLib": ["0x18e47340854f3612974bf5342ba88262a348e589"],
            "SimulateTxAccessor": ["0xfe9c59afbc538185b3412269864192e29c5578f1"],
        },
    }


settings = Settings()

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": SafeJsonFormatter}},  # Custom formatter class
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "json",
        }
    },
    "loggers": {
        "": {
            "level": settings.LOG_LEVEL,
            "handlers": ["console"],
            "propagate": False,
        },
        "app.services.events": {
            "level": settings.LOG_LEVEL_EVENTS_SERVICE,
            "handlers": ["console"],
            "propagate": False,
        },
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
