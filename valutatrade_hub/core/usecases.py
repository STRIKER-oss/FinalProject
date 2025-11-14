"""Бизнес-логика приложения."""
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from ..decorators import log_action
from .models import User, Portfolio, Wallet
from .exceptions import (
    InsufficientFundsError, CurrencyNotFoundError, ApiRequestError,
    UserNotFoundError, UserAlreadyExistsError, InvalidPasswordError,
    WalletNotFoundError, InvalidAmountError, ExchangeRateUnavailableError
)
from .utils import load_json, save_json, validate_currency_code, validate_amount, is_rate_fresh, format_datetime
from .currencies import CurrencyRegistry, get_currency
from ..infra.settings import settings
from ..infra.database import DatabaseManager


class UserManager:
    """Менеджер пользователей."""
    
    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or settings.get_data_dir()
        self.users_file = os.path.join(self.data_dir, "users.json")
        self.database = DatabaseManager()
        self.users: List[User] = self._load_users()
    
    def _load_users(self) -> List[User]:
        """Безопасная загрузка пользователей из файла."""
        try:
            users_data = self.database.load_data(self.users_file, default=[])
            return [User.from_dict(user_data) for user_data in users_data]
        except Exception as e:
            print(f"Error loading users: {e}")
            return []
    
    def save_users(self) -> None:
        """Безопасное сохранение пользователей в файл."""
        try:
            users_data = [user.to_dict() for user in self.users]
            self.database.save_data(users_data, self.users_file)
        except Exception as e:
            print(f"Error saving users: {e}")
            raise
    
    def get_next_user_id(self) -> int:
        """Получение следующего ID пользователя."""
        if not self.users:
            return 1
        return max(user.user_id for user in self.users) + 1
    
    @log_action("REGISTER")
    def register_user(self, username: str, password: str) -> bool:
        """Регистрация нового пользователя."""
        # Валидация входных данных
        if not username or not username.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        
        if not password or len(password) < 4:
            raise ValueError("Пароль должен содержать не менее 4 символов")
        
        # Проверка существования пользователя
        if any(user.username == username for user in self.users):
            raise UserAlreadyExistsError(username)
        
        # Создание нового пользователя
        new_user = User(
            user_id=self.get_next_user_id(),
            username=username,
            password=password
        )
        
        # Безопасное сохранение
        self.users.append(new_user)
        self.save_users()
        
        # Автоматически создаем портфель с 10,000 USD
        portfolio_manager = PortfolioManager(data_dir=self.data_dir, user_manager=self)
        portfolio = portfolio_manager.get_portfolio(new_user.user_id)
        portfolio.add_currency("USD", 10000.0)  # Начисляем 10,000 USD
        portfolio_manager.save_portfolio(portfolio)
        
        return True
    
    @log_action("LOGIN")
    def authenticate_user(self, username: str, password: str) -> bool:
        """Аутентификация пользователя."""
        if not username or not password:
            raise ValueError("Имя пользователя и пароль не могут быть пустыми")
        
        user = self.find_user_by_username(username)
        if not user:
            raise UserNotFoundError(username)
        
        if not user.verify_password(password):
            raise InvalidPasswordError(username)
        
        return True
    
    def find_user_by_username(self, username: str) -> Optional[User]:
        """Поиск пользователя по имени."""
        for user in self.users:
            if user.username == username:
                return user
        return None
    
    def find_user_by_id(self, user_id: int) -> Optional[User]:
        """Поиск пользователя по ID."""
        for user in self.users:
            if user.user_id == user_id:
                return user
        return None
    
    def change_user_password(self, username: str, new_password: str) -> bool:
        """Изменение пароля пользователя."""
        user = self.find_user_by_username(username)
        if not user:
            raise UserNotFoundError(username)
        
        if not new_password or len(new_password) < 4:
            raise ValueError("Пароль должен содержать не менее 4 символов")
        
        user.change_password(new_password)
        self.save_users()
        return True


class PortfolioManager:
    """Менеджер портфелей."""
    
    def __init__(self, data_dir: str = None, user_manager: Optional[UserManager] = None):
        self.data_dir = data_dir or settings.get_data_dir()
        self.portfolios_file = os.path.join(self.data_dir, "portfolios.json")
        self.user_manager = user_manager
        self.database = DatabaseManager()
        self.portfolios: Dict[int, Portfolio] = self._load_portfolios()
        # Добавляем currency_manager
        self.currency_manager = CurrencyManager(data_dir)
    
    def _load_portfolios(self) -> Dict[int, Portfolio]:
        """Безопасная загрузка портфелей из файла."""
        try:
            portfolios_data = self.database.load_data(self.portfolios_file, default=[])
            result = {}
            
            for portfolio_data in portfolios_data:
                user_id = portfolio_data["user_id"]
                user = None
                if self.user_manager:
                    user = self.user_manager.find_user_by_id(user_id)
                
                result[user_id] = Portfolio.from_dict(portfolio_data, user)
            
            return result
        except Exception as e:
            print(f"Error loading portfolios: {e}")
            return {}
    
    def save_portfolios(self) -> None:
        """Безопасное сохранение портфелей в файл."""
        try:
            portfolios_data = [portfolio.to_dict() for portfolio in self.portfolios.values()]
            self.database.save_data(portfolios_data, self.portfolios_file)
        except Exception as e:
            print(f"Error saving portfolios: {e}")
            raise
    
    def get_portfolio(self, user_id: int) -> Portfolio:
        """Получение портфеля пользователя по ID."""
        if user_id not in self.portfolios:
            user = None
            if self.user_manager:
                user = self.user_manager.find_user_by_id(user_id)
            self.portfolios[user_id] = Portfolio(user_id, user)
        return self.portfolios[user_id]
    
    def get_portfolio_by_username(self, username: str) -> Optional[Portfolio]:
        """Получение портфеля пользователя по имени."""
        if not self.user_manager:
            return None
        
        user = self.user_manager.find_user_by_username(username)
        if not user:
            raise UserNotFoundError(username)
        
        return self.get_portfolio(user.user_id)
    
    def save_portfolio(self, portfolio: Portfolio) -> None:
        """Сохранение портфеля."""
        self.portfolios[portfolio.user_id] = portfolio
        self.save_portfolios()
    
    def add_currency_to_portfolio(self, user_id: int, currency_code: str, 
                                 initial_balance: float = 0.0) -> bool:
        """Добавление валюты в портфель пользователя."""
        # Валидация валюты через иерархию валют
        try:
            currency = get_currency(currency_code)
        except CurrencyNotFoundError:
            raise CurrencyNotFoundError(currency_code)
        
        if not validate_amount(initial_balance):
            raise InvalidAmountError(initial_balance)
        
        portfolio = self.get_portfolio(user_id)
        success = portfolio.add_currency(currency_code, initial_balance)
        if success:
            self.save_portfolio(portfolio)
        return success
    
    def deposit_to_wallet(self, user_id: int, currency_code: str, amount: float) -> bool:
        """Пополнение кошелька пользователя."""
        # Валидация валюты через иерархию валют
        try:
            currency = get_currency(currency_code)
        except CurrencyNotFoundError:
            raise CurrencyNotFoundError(currency_code)
        
        if not validate_amount(amount):
            raise InvalidAmountError(amount)
        
        portfolio = self.get_portfolio(user_id)
        success = portfolio.deposit_to_wallet(currency_code, amount)
        if success:
            self.save_portfolio(portfolio)
        return success
    
    def withdraw_from_wallet(self, user_id: int, currency_code: str, amount: float) -> bool:
        """Снятие средств с кошелька пользователя."""
        # Валидация валюты через иерархию валют
        try:
            currency = get_currency(currency_code)
        except CurrencyNotFoundError:
            raise CurrencyNotFoundError(currency_code)
        
        if not validate_amount(amount):
            raise InvalidAmountError(amount)
        
        portfolio = self.get_portfolio(user_id)
        success = portfolio.withdraw_from_wallet(currency_code, amount)
        if success:
            self.save_portfolio(portfolio)
        return success
    
    @log_action("BUY", verbose=True)
    def buy_currency(self, user_id: int, currency_code: str, amount: float) -> bool:
        """Покупка валюты пользователем."""
        # Валидация входных данных
        try:
            currency = get_currency(currency_code)
        except CurrencyNotFoundError:
            raise CurrencyNotFoundError(currency_code)
        
        if not validate_amount(amount):
            raise InvalidAmountError(amount)
        
        # Нельзя покупать USD через эту команду (USD пополняется только при регистрации)
        if currency_code == "USD":
            raise ValueError("Для пополнения USD используйте отдельную команду или обратитесь к администратору")
        
        # Получаем портфель пользователя
        portfolio = self.get_portfolio(user_id)
        
        # Получаем курс для расчета стоимости
        try:
            exchange_rate = self.currency_manager.get_rate("USD", currency_code)
        except (CurrencyNotFoundError, ExchangeRateUnavailableError, ApiRequestError) as e:
            raise e
        
        # Рассчитываем стоимость покупки в USD
        cost_in_usd = amount * exchange_rate
        
        # Проверяем достаточно ли средств в USD кошельке
        usd_balance = portfolio.get_balance("USD")
        if usd_balance < cost_in_usd:
            raise InsufficientFundsError(
                currency_code="USD",
                available=usd_balance,
                required=cost_in_usd
            )
        
        # Выполняем покупку
        success = portfolio.buy_currency("USD", currency_code, amount, exchange_rate)
        if success:
            self.save_portfolio(portfolio)
        
        return success
    
    @log_action("SELL", verbose=True)
    def sell_currency(self, user_id: int, currency_code: str, amount: float) -> bool:
        """Продажа валюты пользователем."""
        # Валидация входных данных
        try:
            currency = get_currency(currency_code)
        except CurrencyNotFoundError:
            raise CurrencyNotFoundError(currency_code)
        
        if not validate_amount(amount):
            raise InvalidAmountError(amount)
        
        # Нельзя продавать USD (только покупать другие валюты за USD)
        if currency_code == "USD":
            raise ValueError("Продажа USD недоступна. Используйте покупку других валют")
        
        # Получаем портфель пользователя
        portfolio = self.get_portfolio(user_id)
        
        # Проверяем наличие кошелька и достаточность средств
        wallet_balance = portfolio.get_balance(currency_code)
        if wallet_balance < amount:
            raise InsufficientFundsError(
                currency_code=currency_code,
                available=wallet_balance,
                required=amount
            )
        
        # Получаем курс для расчета выручки
        try:
            exchange_rate = self.currency_manager.get_rate(currency_code, "USD")
        except (CurrencyNotFoundError, ExchangeRateUnavailableError, ApiRequestError) as e:
            raise e
        
        # Выполняем продажу
        success = portfolio.sell_currency(currency_code, "USD", amount, exchange_rate)
        if success:
            self.save_portfolio(portfolio)
        
        return success
    
    def get_total_portfolio_value(self, user_id: int, exchange_rates: Dict[str, float], 
                                 base_currency: str = 'USD') -> float:
        """Получение общей стоимости портфеля пользователя."""
        portfolio = self.get_portfolio(user_id)
        return portfolio.get_total_value(exchange_rates, base_currency)


class CurrencyManager:
    """Менеджер валютных курсов."""
    
    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or settings.get_data_dir()
        self.rates_file = os.path.join(self.data_dir, "rates.json")
        self.database = DatabaseManager()
        self.rates_data: Dict = self._load_rates()
    
    def _load_rates(self) -> Dict:
        """Безопасная загрузка курсов валют."""
        try:
            return self.database.load_data(self.rates_file, default={})
        except Exception as e:
            print(f"Error loading rates: {e}")
            return {}
    
    def save_rates(self) -> None:
        """Безопасное сохранение курсов валют."""
        try:
            self.database.save_data(self.rates_data, self.rates_file)
        except Exception as e:
            print(f"Error saving rates: {e}")
            raise
    
    def _get_fresh_rate_from_api(self, from_currency: str, to_currency: str) -> Optional[float]:
        """Заглушка для получения свежего курса от API (Parser Service)."""
        # В реальном приложении здесь был бы запрос к Parser Service
        # Имитируем возможные ошибки API
        import random
        if random.random() < 0.1:  # 10% вероятность ошибки API
            raise ApiRequestError("Сервер временно недоступен")
        
        # Для демонстрации используем фиксированные курсы
        mock_rates = {
            "USD_EUR": 0.92,
            "EUR_USD": 1.09,
            "USD_GBP": 0.79,
            "GBP_USD": 1.27,
            "USD_JPY": 148.50,
            "JPY_USD": 0.0067,
            "USD_RUB": 98.42,
            "RUB_USD": 0.01016,
            "USD_CNY": 7.25,
            "CNY_USD": 0.138,
            "USD_BTC": 0.00001685,
            "BTC_USD": 59337.21,
            "USD_ETH": 0.00027,
            "ETH_USD": 3720.00,
            "USD_LTC": 0.0056,
            "LTC_USD": 178.57,
            "USD_XRP": 1.85,
            "XRP_USD": 0.54,
            "USD_ADA": 3.45,
            "ADA_USD": 0.29
        }
        
        pair_key = f"{from_currency}_{to_currency}"
        return mock_rates.get(pair_key)
    
    def _update_rate_in_cache(self, from_currency: str, to_currency: str, rate: float):
        """Обновление курса в кеше."""
        pair_key = f"{from_currency}_{to_currency}"
        current_time = datetime.now().isoformat()
        
        self.rates_data[pair_key] = {
            "rate": rate,
            "updated_at": current_time
        }
        
        # Обновляем общее время обновления
        self.rates_data["last_refresh"] = current_time
        self.save_rates()
    
    def _is_rate_fresh(self, updated_at: str) -> bool:
        """Проверка свежести курса с использованием TTL из настроек."""
        return is_rate_fresh(updated_at, settings.get_rates_ttl())
    
    @log_action("GET_RATE")
    def get_rate(self, from_currency: str, to_currency: str = "USD") -> float:
        """Получение курса валютной пары."""
        if from_currency == to_currency:
            return 1.0
        
        # Валидация валют через иерархию валют
        try:
            from_curr = get_currency(from_currency)
            to_curr = get_currency(to_currency)
        except CurrencyNotFoundError as e:
            raise CurrencyNotFoundError(str(e))
        
        pair_key = f"{from_currency}_{to_currency}"
        reverse_pair_key = f"{to_currency}_{from_currency}"
        
        # Прямой поиск в кеше
        if pair_key in self.rates_data:
            rate_info = self.rates_data[pair_key]
            if isinstance(rate_info, dict) and 'rate' in rate_info:
                # Проверяем свежесть курса
                if 'updated_at' in rate_info and self._is_rate_fresh(rate_info['updated_at']):
                    return rate_info['rate']
                else:
                    # Курс устарел, пытаемся обновить
                    try:
                        fresh_rate = self._get_fresh_rate_from_api(from_currency, to_currency)
                        if fresh_rate:
                            self._update_rate_in_cache(from_currency, to_currency, fresh_rate)
                            return fresh_rate
                        else:
                            # Если не удалось обновить, используем старый курс
                            return rate_info['rate']
                    except ApiRequestError:
                        # Если API недоступно, используем кеш
                        return rate_info['rate']
        
        # Обратный поиск в кеше
        if reverse_pair_key in self.rates_data:
            rate_info = self.rates_data[reverse_pair_key]
            if isinstance(rate_info, dict) and 'rate' in rate_info:
                # Проверяем свежесть курса
                if 'updated_at' in rate_info and self._is_rate_fresh(rate_info['updated_at']):
                    return 1.0 / rate_info['rate']
                else:
                    # Курс устарел, пытаемся обновить
                    try:
                        fresh_rate = self._get_fresh_rate_from_api(to_currency, from_currency)
                        if fresh_rate:
                            self._update_rate_in_cache(to_currency, from_currency, fresh_rate)
                            return 1.0 / fresh_rate
                        else:
                            # Если не удалось обновить, используем старый курс
                            return 1.0 / rate_info['rate']
                    except ApiRequestError:
                        # Если API недоступно, используем кеш
                        return 1.0 / rate_info['rate']
        
        # Конвертация через USD
        if from_currency != "USD" and to_currency != "USD":
            try:
                rate_to_usd = self.get_rate(from_currency, "USD")
                rate_from_usd = self.get_rate("USD", to_currency)
                return rate_to_usd * rate_from_usd
            except (CurrencyNotFoundError, ExchangeRateUnavailableError, ApiRequestError):
                pass
        
        # Пытаемся получить свежий курс от API
        try:
            fresh_rate = self._get_fresh_rate_from_api(from_currency, to_currency)
            if fresh_rate:
                self._update_rate_in_cache(from_currency, to_currency, fresh_rate)
                return fresh_rate
            else:
                raise ExchangeRateUnavailableError(from_currency, to_currency)
        except ApiRequestError as e:
            # Пробрасываем ошибку API наверх
            raise e
    
    def get_rate_with_info(self, from_currency: str, to_currency: str) -> Optional[Dict]:
        """Получение курса с дополнительной информацией."""
        try:
            rate = self.get_rate(from_currency, to_currency)
        except (CurrencyNotFoundError, ApiRequestError, ExchangeRateUnavailableError) as e:
            return None
        
        pair_key = f"{from_currency}_{to_currency}"
        reverse_pair_key = f"{to_currency}_{from_currency}"
        
        updated_at = None
        if pair_key in self.rates_data:
            rate_info = self.rates_data[pair_key]
            if isinstance(rate_info, dict) and 'updated_at' in rate_info:
                updated_at = rate_info['updated_at']
        elif reverse_pair_key in self.rates_data:
            rate_info = self.rates_data[reverse_pair_key]
            if isinstance(rate_info, dict) and 'updated_at' in rate_info:
                updated_at = rate_info['updated_at']
        
        return {
            'rate': rate,
            'updated_at': updated_at,
            'reverse_rate': 1.0 / rate if rate != 0 else None
        }
    
    def get_all_rates(self) -> Dict[str, float]:
        """Получение всех доступных курсов."""
        rates = {}
        for key, value in self.rates_data.items():
            if key not in ['source', 'last_refresh'] and isinstance(value, dict):
                rates[key] = value.get('rate', 0.0)
        return rates
    
    def convert_currency(self, amount: float, from_currency: str, to_currency: str) -> float:
        """Конвертация валюты."""
        rate = self.get_rate(from_currency, to_currency)
        return amount * rate
