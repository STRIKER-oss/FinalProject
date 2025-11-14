"""Иерархия классов валют с наследованием и полиморфизмом."""
from abc import ABC, abstractmethod
from typing import Dict
from .exceptions import CurrencyNotFoundError, InvalidCurrencyCodeError


class Currency(ABC):
    """Абстрактный базовый класс валюты."""
    
    def __init__(self, name: str, code: str):
        self._validate_code(code)
        self._validate_name(name)
        
        self._name = name
        self._code = code.upper()
    
    def _validate_code(self, code: str) -> None:
        """Валидация кода валюты."""
        if not isinstance(code, str):
            raise InvalidCurrencyCodeError(code, "Код должен быть строкой")
        if not (2 <= len(code) <= 5):
            raise InvalidCurrencyCodeError(code, "Длина кода должна быть от 2 до 5 символов")
        if not code.isalnum():
            raise InvalidCurrencyCodeError(code, "Код должен содержать только буквы и цифры")
        if ' ' in code:
            raise InvalidCurrencyCodeError(code, "Код не должен содержать пробелы")
    
    def _validate_name(self, name: str) -> None:
        """Валидация названия валюты."""
        if not isinstance(name, str):
            raise ValueError("Название должно быть строкой")
        if not name.strip():
            raise ValueError("Название не может быть пустой строкой")
    
    @property
    def name(self) -> str:
        """Человекочитаемое имя валюты."""
        return self._name
    
    @property
    def code(self) -> str:
        """ISO-код или общепринятый тикер."""
        return self._code
    
    @abstractmethod
    def get_display_info(self) -> str:
        """Строковое представление для UI/логов."""
        pass
    
    def __str__(self) -> str:
        return f"{self._code} - {self._name}"
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self._name}', code='{self._code}')"


class FiatCurrency(Currency):
    """Класс фиатной валюты."""
    
    def __init__(self, name: str, code: str, issuing_country: str):
        super().__init__(name, code)
        self._issuing_country = issuing_country
    
    @property
    def issuing_country(self) -> str:
        """Страна или зона эмиссии."""
        return self._issuing_country
    
    def get_display_info(self) -> str:
        """Строковое представление фиатной валюты."""
        return f"[FIAT] {self._code} — {self._name} (Issuing: {self._issuing_country})"
    
    def __repr__(self) -> str:
        return (f"{self.__class__.__name__}(name='{self._name}', "
                f"code='{self._code}', issuing_country='{self._issuing_country}')")


class CryptoCurrency(Currency):
    """Класс криптовалюты."""
    
    def __init__(self, name: str, code: str, algorithm: str, market_cap: float):
        super().__init__(name, code)
        self._algorithm = algorithm
        self._market_cap = market_cap
    
    @property
    def algorithm(self) -> str:
        """Алгоритм консенсуса/хэширования."""
        return self._algorithm
    
    @property
    def market_cap(self) -> float:
        """Рыночная капитализация."""
        return self._market_cap
    
    def get_display_info(self) -> str:
        """Строковое представление криптовалюты."""
        # Форматируем капитализацию в читаемом виде
        if self._market_cap >= 1e12:
            mcap_str = f"{self._market_cap / 1e12:.2f}T"
        elif self._market_cap >= 1e9:
            mcap_str = f"{self._market_cap / 1e9:.2f}B"
        elif self._market_cap >= 1e6:
            mcap_str = f"{self._market_cap / 1e6:.2f}M"
        else:
            mcap_str = f"{self._market_cap:.2f}"
        
        return f"[CRYPTO] {self._code} — {self._name} (Algo: {self._algorithm}, MCAP: {mcap_str})"
    
    def __repr__(self) -> str:
        return (f"{self.__class__.__name__}(name='{self._name}', code='{self._code}', "
                f"algorithm='{self._algorithm}', market_cap={self._market_cap})")


class CurrencyRegistry:
    """Реестр валют с фабричными методами."""
    
    # Реестр известных валют
    _CURRENCY_REGISTRY: Dict[str, Dict] = {
        # Фиатные валюты
        "USD": {
            "type": "fiat",
            "name": "US Dollar",
            "issuing_country": "United States"
        },
        "EUR": {
            "type": "fiat", 
            "name": "Euro",
            "issuing_country": "Eurozone"
        },
        "GBP": {
            "type": "fiat",
            "name": "British Pound", 
            "issuing_country": "United Kingdom"
        },
        "JPY": {
            "type": "fiat",
            "name": "Japanese Yen",
            "issuing_country": "Japan"
        },
        "RUB": {
            "type": "fiat",
            "name": "Russian Ruble",
            "issuing_country": "Russia"
        },
        "CNY": {
            "type": "fiat",
            "name": "Chinese Yuan",
            "issuing_country": "China"
        },
        
        # Криптовалюты
        "BTC": {
            "type": "crypto",
            "name": "Bitcoin",
            "algorithm": "SHA-256",
            "market_cap": 1.12e12  # Примерная капитализация
        },
        "ETH": {
            "type": "crypto",
            "name": "Ethereum", 
            "algorithm": "Ethash",
            "market_cap": 4.20e11  # Примерная капитализация
        },
        "LTC": {
            "type": "crypto",
            "name": "Litecoin",
            "algorithm": "Scrypt", 
            "market_cap": 6.5e9  # Примерная капитализация
        },
        "XRP": {
            "type": "crypto",
            "name": "Ripple",
            "algorithm": "RPCA",
            "market_cap": 3.4e10  # Примерная капитализация
        },
        "ADA": {
            "type": "crypto", 
            "name": "Cardano",
            "algorithm": "Ouroboros",
            "market_cap": 1.5e10  # Примерная капитализация
        }
    }
    
    @classmethod
    def get_currency(cls, code: str) -> Currency:
        """Фабричный метод для получения валюты по коду."""
        code_upper = code.upper()
        
        if code_upper not in cls._CURRENCY_REGISTRY:
            raise CurrencyNotFoundError(code_upper)
        
        currency_data = cls._CURRENCY_REGISTRY[code_upper]
        
        if currency_data["type"] == "fiat":
            return FiatCurrency(
                name=currency_data["name"],
                code=code_upper,
                issuing_country=currency_data["issuing_country"]
            )
        elif currency_data["type"] == "crypto":
            return CryptoCurrency(
                name=currency_data["name"],
                code=code_upper,
                algorithm=currency_data["algorithm"],
                market_cap=currency_data["market_cap"]
            )
        else:
            raise ValueError(f"Неизвестный тип валюты: {currency_data['type']}")
    
    @classmethod
    def is_currency_supported(cls, code: str) -> bool:
        """Проверка поддержки валюты по коду."""
        return code.upper() in cls._CURRENCY_REGISTRY
    
    @classmethod
    def get_supported_currencies(cls) -> Dict[str, Dict]:
        """Получение словаря поддерживаемых валют."""
        return cls._CURRENCY_REGISTRY.copy()
    
    @classmethod
    def get_supported_fiat_currencies(cls) -> Dict[str, FiatCurrency]:
        """Получение словаря поддерживаемых фиатных валют."""
        return {code: cls.get_currency(code) for code, data in cls._CURRENCY_REGISTRY.items()
                if data["type"] == "fiat"}
    
    @classmethod
    def get_supported_crypto_currencies(cls) -> Dict[str, CryptoCurrency]:
        """Получение словаря поддерживаемых криптовалют."""
        return {code: cls.get_currency(code) for code, data in cls._CURRENCY_REGISTRY.items()
                if data["type"] == "crypto"}


# Функция для удобного использования
def get_currency(code: str) -> Currency:
    """Получить валюту по коду."""
    return CurrencyRegistry.get_currency(code)
