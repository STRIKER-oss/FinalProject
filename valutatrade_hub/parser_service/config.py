"""Конфигурация Parser Service."""
import os
from dataclasses import dataclass, field
from typing import Dict, Tuple


@dataclass
class ParserConfig:
    EXCHANGERATE_API_KEY: str = os.getenv("EXCHANGERATE_API_KEY", "2c2b17168331f142587e9eb3")
    
    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"
    
    BASE_CURRENCY: str = "USD"
    FIAT_CURRENCIES: Tuple[str, ...] = ("EUR", "GBP", "JPY", "RUB", "CNY")
    CRYPTO_CURRENCIES: Tuple[str, ...] = ("BTC", "ETH", "LTC", "XRP", "ADA")
    
    CRYPTO_ID_MAP: Dict[str, str] = field(default_factory=lambda: {
        "BTC": "bitcoin",
        "ETH": "ethereum", 
        "LTC": "litecoin",
        "XRP": "ripple",
        "ADA": "cardano"
    })
    
    REQUEST_TIMEOUT: int = 10
    MAX_RETRIES: int = 3
    RETRY_DELAY: int = 2
    
    RATES_FILE_PATH: str = "data/rates.json"
    HISTORY_FILE_PATH: str = "data/exchange_rates.json"
    
    UPDATE_INTERVAL_MINUTES: int = 5
    RATES_TTL_MINUTES: int = 10
    
    def get_exchangerate_api_url(self) -> str:
        return f"{self.EXCHANGERATE_API_URL}/{self.EXCHANGERATE_API_KEY}/latest/{self.BASE_CURRENCY}"
    
    def get_coingecko_url(self) -> str:
        crypto_ids = ",".join(self.CRYPTO_ID_MAP.values())
        return f"{self.COINGECKO_URL}?ids={crypto_ids}&vs_currencies=usd"
    
    def validate_config(self) -> None:
        if not self.EXCHANGERATE_API_KEY:
            raise ValueError("EXCHANGERATE_API_KEY не установлен")
        
        if not self.FIAT_CURRENCIES:
            raise ValueError("Список фиатных валют не может быть пустым")
            
        if not self.CRYPTO_CURRENCIES:
            raise ValueError("Список криптовалют не может быть пустым")
        
        if len(self.CRYPTO_CURRENCIES) != len(self.CRYPTO_ID_MAP):
            raise ValueError("Количество криптовалют не совпадает с CRYPTO_ID_MAP")
        
        for crypto in self.CRYPTO_CURRENCIES:
            if crypto not in self.CRYPTO_ID_MAP:
                raise ValueError(f"Криптовалюта {crypto} отсутствует в CRYPTO_ID_MAP")


config = ParserConfig()
