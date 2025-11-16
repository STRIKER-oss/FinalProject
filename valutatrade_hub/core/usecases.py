"""Бизнес-логика приложения."""
import os
from datetime import datetime
from typing import Dict, Optional
from ..decorators import log_action
from .models import User, Portfolio
from .exceptions import (
    InsufficientFundsError, CurrencyNotFoundError, ApiRequestError,
    UserNotFoundError, UserAlreadyExistsError, InvalidPasswordError,
    WalletNotFoundError, InvalidAmountError, ExchangeRateUnavailableError
)
from .utils import is_rate_fresh
from .currencies import get_currency
from ..infra.settings import settings
from ..infra.database import DatabaseManager


class UserManager:
    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or settings.get_data_dir()
        self.users_file = os.path.join(self.data_dir, "users.json")
        self.database = DatabaseManager()
        self.users: list[User] = self._load_users()
    
    def _load_users(self) -> list[User]:
        try:
            users_data = self.database.load_data(self.users_file, default=[])
            return [User.from_dict(user_data) for user_data in users_data]
        except Exception:
            return []
    
    def save_users(self) -> None:
        try:
            users_data = [user.to_dict() for user in self.users]
            self.database.save_data(users_data, self.users_file)
        except Exception:
            raise
    
    def get_next_user_id(self) -> int:
        if not self.users:
            return 1
        return max(user.user_id for user in self.users) + 1
    
    @log_action("REGISTER")
    def register_user(self, username: str, password: str) -> bool:
        if not username or not username.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        
        if not password or len(password) < 4:
            raise ValueError("Пароль должен содержать не менее 4 символов")
        
        if any(user.username == username for user in self.users):
            raise UserAlreadyExistsError(username)
        
        new_user_id = self.get_next_user_id()
        new_user = User(
            user_id=new_user_id,
            username=username,
            password=password
        )
        
        self.users.append(new_user)
        self.save_users()
        
        portfolio_manager = PortfolioManager(data_dir=self.data_dir, user_manager=self)
        portfolio = portfolio_manager.get_portfolio(new_user_id)
        
        success = portfolio.add_currency("USD", 10000.0)
        if not success:
            usd_wallet = portfolio.get_wallet("USD")
            if usd_wallet:
                usd_wallet.balance = 10000.0
        
        portfolio_manager.save_portfolio(portfolio)
        
        return True
    
    @log_action("LOGIN")
    def authenticate_user(self, username: str, password: str) -> bool:
        if not username or not password:
            raise ValueError("Имя пользователя и пароль не могут быть пустыми")
        
        user = self.find_user_by_username(username)
        if not user:
            raise UserNotFoundError(username)
        
        if not user.verify_password(password):
            raise InvalidPasswordError(username)
        
        return True
    
    def find_user_by_username(self, username: str) -> Optional[User]:
        for user in self.users:
            if user.username == username:
                return user
        return None
    
    def find_user_by_id(self, user_id: int) -> Optional[User]:
        for user in self.users:
            if user.user_id == user_id:
                return user
        return None
    
    def change_user_password(self, username: str, new_password: str) -> bool:
        user = self.find_user_by_username(username)
        if not user:
            raise UserNotFoundError(username)
        
        if not new_password or len(new_password) < 4:
            raise ValueError("Пароль должен содержать не менее 4 символов")
        
        user.change_password(new_password)
        self.save_users()
        return True


class PortfolioManager:
    def __init__(self, data_dir: str = None, user_manager: Optional[UserManager] = None):
        self.data_dir = data_dir or settings.get_data_dir()
        self.portfolios_file = os.path.join(self.data_dir, "portfolios.json")
        self.user_manager = user_manager
        self.database = DatabaseManager()
        self.portfolios: Dict[int, Portfolio] = self._load_portfolios()
        self.currency_manager = CurrencyManager(data_dir)
    
    def _load_portfolios(self) -> Dict[int, Portfolio]:
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
        except Exception:
            return {}
    
    def save_portfolios(self) -> None:
        try:
            portfolios_data = [portfolio.to_dict() for portfolio in self.portfolios.values()]
            self.database.save_data(portfolios_data, self.portfolios_file)
        except Exception:
            raise
    
    def get_portfolio(self, user_id: int) -> Portfolio:
        if user_id not in self.portfolios:
            try:
                portfolios_data = self.database.load_data(self.portfolios_file, default=[])
                for portfolio_data in portfolios_data:
                    if portfolio_data["user_id"] == user_id:
                        user = None
                        if self.user_manager:
                            user = self.user_manager.find_user_by_id(user_id)
                        self.portfolios[user_id] = Portfolio.from_dict(portfolio_data, user)
                        return self.portfolios[user_id]
            except Exception:
                pass
                    
            user = None
            if self.user_manager:
                user = self.user_manager.find_user_by_id(user_id)
            self.portfolios[user_id] = Portfolio(user_id, user)
        return self.portfolios[user_id]
    
    def get_portfolio_by_username(self, username: str) -> Optional[Portfolio]:
        if not self.user_manager:
            return None
        
        user = self.user_manager.find_user_by_username(username)
        if not user:
            raise UserNotFoundError(username)
        
        return self.get_portfolio(user.user_id)
    
    def save_portfolio(self, portfolio: Portfolio) -> None:
        self.portfolios[portfolio.user_id] = portfolio
        self.save_portfolios()
    
    def add_currency_to_portfolio(self, user_id: int, currency_code: str, 
                                 initial_balance: float = 0.0) -> bool:
        get_currency(currency_code)
        
        if not self._validate_amount(initial_balance):
            raise InvalidAmountError(initial_balance)
        
        portfolio = self.get_portfolio(user_id)
        success = portfolio.add_currency(currency_code, initial_balance)
        if success:
            self.save_portfolio(portfolio)
        return success
    
    def deposit_to_wallet(self, user_id: int, currency_code: str, amount: float) -> bool:
        get_currency(currency_code)
        
        if not self._validate_amount(amount):
            raise InvalidAmountError(amount)
        
        portfolio = self.get_portfolio(user_id)
        success = portfolio.deposit_to_wallet(currency_code, amount)
        if success:
            self.save_portfolio(portfolio)
        return success
    
    def withdraw_from_wallet(self, user_id: int, currency_code: str, amount: float) -> bool:
        get_currency(currency_code)
        
        if not self._validate_amount(amount):
            raise InvalidAmountError(amount)
        
        portfolio = self.get_portfolio(user_id)
        success = portfolio.withdraw_from_wallet(currency_code, amount)
        if success:
            self.save_portfolio(portfolio)
        return success
    
    @log_action("BUY", verbose=True)
    def buy_currency(self, user_id: int, currency_code: str, amount: float) -> bool:
        get_currency(currency_code)
        
        if not self._validate_amount(amount):
            raise InvalidAmountError(amount)
        
        if currency_code == "USD":
            raise ValueError("Для пополнения USD используйте отдельную команду")
        
        portfolio = self.get_portfolio(user_id)
        
        try:
            exchange_rate = self.currency_manager.get_rate("USD", currency_code)
            cost_in_usd = amount / exchange_rate
            
        except (CurrencyNotFoundError, ExchangeRateUnavailableError, ApiRequestError) as e:
            raise e
        
        usd_balance = portfolio.get_balance("USD")
        if usd_balance < cost_in_usd:
            raise InsufficientFundsError(
                currency_code="USD",
                available=usd_balance,
                required=cost_in_usd
            )
        
        usd_wallet = portfolio.get_wallet("USD")
        if not usd_wallet:
            raise WalletNotFoundError("USD")
        
        if not usd_wallet.withdraw(cost_in_usd):
            raise InsufficientFundsError(
                currency_code="USD",
                available=usd_wallet.balance,
                required=cost_in_usd
            )
        
        target_wallet = portfolio.get_wallet(currency_code)
        if target_wallet:
            target_wallet.deposit(amount)
        else:
            portfolio.add_currency(currency_code, amount)
        
        self.save_portfolio(portfolio)
        return True
    
    @log_action("SELL", verbose=True)
    def sell_currency(self, user_id: int, currency_code: str, amount: float) -> bool:
        get_currency(currency_code)
        
        if not self._validate_amount(amount):
            raise InvalidAmountError(amount)
        
        if currency_code == "USD":
            raise ValueError("Продажа USD недоступна")
        
        portfolio = self.get_portfolio(user_id)
        
        wallet_balance = portfolio.get_balance(currency_code)
        if wallet_balance < amount:
            raise InsufficientFundsError(
                currency_code=currency_code,
                available=wallet_balance,
                required=amount
            )
        
        try:
            exchange_rate = self.currency_manager.get_rate(currency_code, "USD")
            usd_revenue = amount * exchange_rate
            
        except (CurrencyNotFoundError, ExchangeRateUnavailableError, ApiRequestError) as e:
            raise e
        
        from_wallet = portfolio.get_wallet(currency_code)
        if not from_wallet:
            raise WalletNotFoundError(currency_code)
        
        if not from_wallet.withdraw(amount):
            raise InsufficientFundsError(
                currency_code=currency_code,
                available=from_wallet.balance,
                required=amount
            )
        
        usd_wallet = portfolio.get_wallet("USD")
        if usd_wallet:
            usd_wallet.deposit(usd_revenue)
        else:
            portfolio.add_currency("USD", usd_revenue)
        
        self.save_portfolio(portfolio)
        return True
    
    def get_total_portfolio_value(self, user_id: int, exchange_rates: Dict[str, float], 
                                 base_currency: str = 'USD') -> float:
        portfolio = self.get_portfolio(user_id)
        return portfolio.get_total_value(exchange_rates, base_currency)
    
    def _validate_amount(self, amount: float) -> bool:
        return isinstance(amount, (int, float)) and amount > 0


class CurrencyManager:
    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or settings.get_data_dir()
        self.rates_file = os.path.join(self.data_dir, "rates.json")
        self.database = DatabaseManager()
        self.rates_data: Dict = self._load_rates()
    
    def _load_rates(self) -> Dict:
        try:
            return self.database.load_data(self.rates_file, default={})
        except Exception:
            return {}
    
    def save_rates(self) -> None:
        try:
            self.database.save_data(self.rates_data, self.rates_file)
        except Exception:
            raise
    
    def _get_fresh_rate_from_api(self, from_currency: str, to_currency: str) -> Optional[float]:
        try:
            from ..parser_service.storage import RatesStorage
            from ..parser_service.updater import RatesUpdater
            
            storage = RatesStorage()
            
            current_rates = storage.load_current_rates()
            
            if current_rates and 'pairs' in current_rates and 'last_refresh' in current_rates:
                if is_rate_fresh(current_rates['last_refresh'], settings.get_rates_ttl()):
                    rate = self._find_rate_in_pairs(current_rates['pairs'], from_currency, to_currency)
                    if rate is not None:
                        return rate
            
            updater = RatesUpdater()
            result = updater.run_update()
            
            if result and 'pairs' in result:
                rate = self._find_rate_in_pairs(result['pairs'], from_currency, to_currency)
                if rate is not None:
                    return rate
            
            updated_rates = storage.load_current_rates()
            if updated_rates and 'pairs' in updated_rates:
                rate = self._find_rate_in_pairs(updated_rates['pairs'], from_currency, to_currency)
                if rate is not None:
                    return rate
            
            raise ExchangeRateUnavailableError(from_currency, to_currency)
            
        except Exception:
            raise ExchangeRateUnavailableError(from_currency, to_currency)

    def _find_rate_in_pairs(self, pairs: Dict, from_currency: str, to_currency: str) -> Optional[float]:
        pair_key = f"{from_currency}_{to_currency}"
        if pair_key in pairs:
            rate_info = pairs[pair_key]
            if isinstance(rate_info, dict) and 'rate' in rate_info:
                return rate_info['rate']
        
        reverse_pair_key = f"{to_currency}_{from_currency}"
        if reverse_pair_key in pairs:
            rate_info = pairs[reverse_pair_key]
            if isinstance(rate_info, dict) and 'rate' in rate_info:
                return 1.0 / rate_info['rate']
        
        return None
    
    def _update_rate_in_cache(self, from_currency: str, to_currency: str, rate: float):
        pair_key = f"{from_currency}_{to_currency}"
        current_time = datetime.now().isoformat()
        
        self.rates_data[pair_key] = {
            "rate": rate,
            "updated_at": current_time
        }
        
        self.rates_data["last_refresh"] = current_time
        self.save_rates()
    
    def _is_rate_fresh(self, updated_at: str) -> bool:
        return is_rate_fresh(updated_at, settings.get_rates_ttl())
    
    @log_action("GET_RATE")
    def get_rate(self, from_currency: str, to_currency: str = "USD") -> float:
        if from_currency == to_currency:
            return 1.0
        
        get_currency(from_currency)
        get_currency(to_currency)
        
        pair_key = f"{from_currency}_{to_currency}"
        reverse_pair_key = f"{to_currency}_{from_currency}"
        
        if pair_key in self.rates_data:
            rate_info = self.rates_data[pair_key]
            if isinstance(rate_info, dict) and 'rate' in rate_info:
                if 'updated_at' in rate_info and self._is_rate_fresh(rate_info['updated_at']):
                    return rate_info['rate']
                else:
                    try:
                        fresh_rate = self._get_fresh_rate_from_api(from_currency, to_currency)
                        if fresh_rate:
                            self._update_rate_in_cache(from_currency, to_currency, fresh_rate)
                            return fresh_rate
                        else:
                            return rate_info['rate']
                    except ApiRequestError:
                        return rate_info['rate']
        
        if reverse_pair_key in self.rates_data:
            rate_info = self.rates_data[reverse_pair_key]
            if isinstance(rate_info, dict) and 'rate' in rate_info:
                if 'updated_at' in rate_info and self._is_rate_fresh(rate_info['updated_at']):
                    return 1.0 / rate_info['rate']
                else:
                    try:
                        fresh_rate = self._get_fresh_rate_from_api(to_currency, from_currency)
                        if fresh_rate:
                            self._update_rate_in_cache(to_currency, from_currency, fresh_rate)
                            return 1.0 / fresh_rate
                        else:
                            return 1.0 / rate_info['rate']
                    except ApiRequestError:
                        return 1.0 / rate_info['rate']
        
        if from_currency != "USD" and to_currency != "USD":
            try:
                rate_to_usd = self.get_rate(from_currency, "USD")
                rate_from_usd = self.get_rate("USD", to_currency)
                return rate_to_usd * rate_from_usd
            except (CurrencyNotFoundError, ExchangeRateUnavailableError, ApiRequestError):
                pass
        
        try:
            fresh_rate = self._get_fresh_rate_from_api(from_currency, to_currency)
            if fresh_rate:
                self._update_rate_in_cache(from_currency, to_currency, fresh_rate)
                return fresh_rate
            else:
                raise ExchangeRateUnavailableError(from_currency, to_currency)
        except ApiRequestError as e:
            raise e
    
    def get_rate_with_info(self, from_currency: str, to_currency: str) -> Optional[Dict]:
        try:
            rate = self.get_rate(from_currency, to_currency)
        except (CurrencyNotFoundError, ApiRequestError, ExchangeRateUnavailableError):
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
        rates = {}
        for key, value in self.rates_data.items():
            if key not in ['source', 'last_refresh'] and isinstance(value, dict):
                rates[key] = value.get('rate', 0.0)
        return rates
    
    def convert_currency(self, amount: float, from_currency: str, to_currency: str) -> float:
        rate = self.get_rate(from_currency, to_currency)
        return amount * rate
