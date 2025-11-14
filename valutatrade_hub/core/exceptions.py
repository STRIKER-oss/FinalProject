"""Пользовательские исключения для приложения."""


class ValutatradeError(Exception):
    """Базовое исключение приложения."""
    pass


class CurrencyError(ValutatradeError):
    """Ошибки связанные с валютами."""
    pass


class CurrencyNotFoundError(CurrencyError):
    """Валюта не найдена в реестре."""
    
    def __init__(self, currency_code: str):
        super().__init__(f"Неизвестная валюта '{currency_code}'")
        self.currency_code = currency_code


class InvalidCurrencyCodeError(CurrencyError):
    """Неверный формат кода валюты."""
    
    def __init__(self, currency_code: str, reason: str = ""):
        message = f"Неверный формат кода валюты: '{currency_code}'"
        if reason:
            message += f" ({reason})"
        super().__init__(message)
        self.currency_code = currency_code
        self.reason = reason


class UserError(ValutatradeError):
    """Ошибки связанные с пользователями."""
    pass


class UserNotFoundError(UserError):
    """Пользователь не найден."""
    
    def __init__(self, username: str):
        super().__init__(f"Пользователь '{username}' не найден")
        self.username = username


class UserAlreadyExistsError(UserError):
    """Пользователь уже существует."""
    
    def __init__(self, username: str):
        super().__init__(f"Пользователь '{username}' уже существует")
        self.username = username


class AuthenticationError(UserError):
    """Ошибка аутентификации."""
    pass


class InvalidPasswordError(AuthenticationError):
    """Неверный пароль."""
    
    def __init__(self, username: str):
        super().__init__(f"Неверный пароль для пользователя '{username}'")
        self.username = username


class PortfolioError(ValutatradeError):
    """Ошибки связанные с портфелями."""
    pass


class WalletNotFoundError(PortfolioError):
    """Кошелек не найден."""
    
    def __init__(self, currency_code: str):
        super().__init__(f"Кошелек '{currency_code}' не найден")
        self.currency_code = currency_code


class InsufficientFundsError(PortfolioError):
    """Недостаточно средств."""
    
    def __init__(self, currency_code: str, available: float, required: float):
        super().__init__(
            f"Недостаточно средств: доступно {available:.4f} {currency_code}, "
            f"требуется {required:.4f} {currency_code}"
        )
        self.currency_code = currency_code
        self.available = available
        self.required = required


class TradingError(ValutatradeError):
    """Ошибки торговых операций."""
    pass


class InvalidAmountError(TradingError):
    """Неверная сумма."""
    
    def __init__(self, amount: float):
        super().__init__(f"Неверная сумма: {amount}")
        self.amount = amount


class ExchangeRateError(ValutatradeError):
    """Ошибки получения курсов валют."""
    pass


class ExchangeRateUnavailableError(ExchangeRateError):
    """Курс валюты недоступен."""
    
    def __init__(self, from_currency: str, to_currency: str):
        super().__init__(f"Курс {from_currency}→{to_currency} недоступен")
        self.from_currency = from_currency
        self.to_currency = to_currency


class ApiRequestError(ExchangeRateError):
    """Сбой внешнего API."""
    
    def __init__(self, reason: str = ""):
        message = "Ошибка при обращении к внешнему API"
        if reason:
            message += f": {reason}"
        super().__init__(message)
        self.reason = reason


class DatabaseError(ValutatradeError):
    """Ошибки работы с базой данных."""
    pass


class ConfigError(ValutatradeError):
    """Ошибки конфигурации."""
    pass
