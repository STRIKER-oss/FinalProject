"""Модели данных для валютного кошелька."""
import hashlib
from datetime import datetime
from typing import Dict, Optional
from .exceptions import InsufficientFundsError, InvalidAmountError
from .currencies import get_currency


class Wallet:
    def __init__(self, currency_code: str, balance: float = 0.0):
        self._currency_code = currency_code.upper()
        self._balance = float(balance)
        
        self._validate_initial_state()
    
    def _validate_initial_state(self) -> None:
        try:
            get_currency(self._currency_code)
        except Exception as e:
            raise ValueError(f"Неверный код валюты: {self._currency_code}") from e
        
        if self._balance < 0:
            raise ValueError("Начальный баланс не может быть отрицательным")
    
    @property
    def currency_code(self) -> str:
        return self._currency_code
    
    @property
    def balance(self) -> float:
        return self._balance
    
    @balance.setter
    def balance(self, value: float) -> None:
        if not isinstance(value, (int, float)):
            raise ValueError("Баланс должен быть числом")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным")
        
        self._balance = float(value)
    
    def deposit(self, amount: float) -> None:
        if not isinstance(amount, (int, float)):
            raise InvalidAmountError(amount)
        if amount <= 0:
            raise InvalidAmountError(amount)
        
        self._balance += amount
    
    def withdraw(self, amount: float) -> bool:
        if not isinstance(amount, (int, float)):
            raise InvalidAmountError(amount)
        if amount <= 0:
            raise InvalidAmountError(amount)
        
        if amount > self._balance:
            raise InsufficientFundsError(
                currency_code=self._currency_code,
                available=self._balance,
                required=amount
            )
        
        self._balance -= amount
        return True
    
    def get_balance_info(self) -> Dict[str, str]:
        return {
            "currency_code": self._currency_code,
            "balance": f"{self._balance:.2f}",
            "balance_raw": self._balance
        }
    
    def to_dict(self) -> Dict:
        return {
            "currency_code": self._currency_code,
            "balance": self._balance
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Wallet':
        return cls(
            currency_code=data["currency_code"],
            balance=data["balance"]
        )


class Portfolio:
    def __init__(self, user_id: int, user: Optional['User'] = None):
        self._user_id = user_id
        self._user = user
        self._wallets: Dict[str, Wallet] = {}
    
    @property
    def user_id(self) -> int:
        return self._user_id
    
    @property
    def user(self) -> Optional['User']:
        return self._user
    
    @property
    def wallets(self) -> Dict[str, Wallet]:
        return self._wallets.copy()
    
    def get_balance(self, currency_code: str) -> float:
        wallet = self.get_wallet(currency_code)
        return wallet.balance if wallet else 0.0
    
    def add_currency(self, currency_code: str, initial_balance: float = 0.0) -> bool:
        currency_code = currency_code.upper()
        if currency_code in self._wallets:
            return False
        
        wallet = Wallet(currency_code, initial_balance)
        self._wallets[currency_code] = wallet
        return True
    
    def get_wallet(self, currency_code: str) -> Optional[Wallet]:
        return self._wallets.get(currency_code.upper())
    
    def get_total_value(self, exchange_rates: Dict[str, float], base_currency: str = 'USD') -> float:
        total_value = 0.0
        
        for currency_code, wallet in self._wallets.items():
            if currency_code == base_currency:
                total_value += wallet.balance
            elif currency_code in exchange_rates and base_currency in exchange_rates:
                rate_to_usd = exchange_rates[currency_code]
                rate_from_usd_to_base = exchange_rates[base_currency]
                value_in_base = (wallet.balance / rate_to_usd) * rate_from_usd_to_base
                total_value += value_in_base
        
        return total_value
    
    def deposit_to_wallet(self, currency_code: str, amount: float) -> bool:
        wallet = self.get_wallet(currency_code)
        if not wallet:
            self.add_currency(currency_code, 0.0)
            wallet = self.get_wallet(currency_code)
        
        try:
            wallet.deposit(amount)
            return True
        except (ValueError, InvalidAmountError):
            return False
    
    def withdraw_from_wallet(self, currency_code: str, amount: float) -> bool:
        wallet = self.get_wallet(currency_code)
        if not wallet:
            return False
        
        return wallet.withdraw(amount)
    
    def buy_currency(self, from_currency: str, to_currency: str, amount: float, 
                    exchange_rate: float) -> bool:
        cost_in_usd = amount * exchange_rate
        
        usd_wallet = self.get_wallet(from_currency)
        if not usd_wallet or usd_wallet.balance < cost_in_usd:
            return False
        
        if not usd_wallet.withdraw(cost_in_usd):
            return False
        
        target_wallet = self.get_wallet(to_currency)
        if target_wallet:
            target_wallet.deposit(amount)
        else:
            self.add_currency(to_currency, amount)
        
        return True
    
    def sell_currency(self, from_currency: str, to_currency: str, amount: float,
                     exchange_rate: float) -> bool:
        from_wallet = self.get_wallet(from_currency)
        if not from_wallet or from_wallet.balance < amount:
            return False
        
        revenue_in_usd = amount * exchange_rate
        
        if not from_wallet.withdraw(amount):
            return False
        
        usd_wallet = self.get_wallet(to_currency)
        if usd_wallet:
            usd_wallet.deposit(revenue_in_usd)
        else:
            self.add_currency(to_currency, revenue_in_usd)
        
        return True
    
    def get_all_balances(self) -> Dict[str, float]:
        return {code: wallet.balance for code, wallet in self._wallets.items()}
    
    def to_dict(self) -> Dict:
        return {
            "user_id": self._user_id,
            "wallets": {code: wallet.to_dict() for code, wallet in self._wallets.items()}
        }
    
    @classmethod
    def from_dict(cls, data: Dict, user: Optional['User'] = None) -> 'Portfolio':
        portfolio = cls(user_id=data["user_id"], user=user)
        for code, wallet_data in data.get("wallets", {}).items():
            portfolio._wallets[code] = Wallet.from_dict(wallet_data)
        return portfolio


class User:
    def __init__(self, user_id: int, username: str, password: str, 
                 salt: Optional[str] = None, registration_date: Optional[datetime] = None):
        self._user_id = user_id
        self._username = username.strip()
        self._salt = salt or self._generate_salt()
        self._hashed_password = self._hash_password(password, self._salt)
        self._registration_date = registration_date or datetime.now()
        
        self._validate_initial_state(password)
    
    def _validate_initial_state(self, password: str) -> None:
        if not self._username:
            raise ValueError("Имя пользователя не может быть пустым")
        
        if len(self._username) < 3:
            raise ValueError("Имя пользователя должно содержать не менее 3 символов")
        
        if len(password) < 4:
            raise ValueError("Пароль должен содержать не менее 4 символов")
        
        forbidden_names = ['admin', 'root', 'system']
        if self._username.lower() in forbidden_names:
            raise ValueError("Это имя пользователя запрещено")
    
    @property
    def user_id(self) -> int:
        return self._user_id
    
    @user_id.setter
    def user_id(self, value: int) -> None:
        if not isinstance(value, int) or value <= 0:
            raise ValueError("ID пользователя должен быть положительным целым числом")
        
        self._user_id = value
    
    @property
    def username(self) -> str:
        return self._username
    
    @username.setter
    def username(self, value: str) -> None:
        if not value or not value.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        
        self._username = value.strip()
    
    @property
    def hashed_password(self) -> str:
        return self._hashed_password
    
    @property
    def salt(self) -> str:
        return self._salt
    
    @property
    def registration_date(self) -> datetime:
        return self._registration_date
    
    def _generate_salt(self) -> str:
        return hashlib.sha256(str(datetime.now().timestamp()).encode()).hexdigest()[:8]
    
    def _hash_password(self, password: str, salt: str) -> str:
        if len(password) < 4:
            raise ValueError("Пароль должен содержать не менее 4 символов")
        
        return hashlib.sha256((password + salt).encode()).hexdigest()
    
    def get_user_info(self) -> Dict[str, str]:
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat()
        }
    
    def change_password(self, new_password: str) -> None:
        if len(new_password) < 4:
            raise ValueError("Пароль должен содержать не менее 4 символов")
        
        self._salt = self._generate_salt()
        self._hashed_password = self._hash_password(new_password, self._salt)
    
    def verify_password(self, password: str) -> bool:
        hashed_input = self._hash_password(password, self._salt)
        return hashed_input == self._hashed_password
    
    def to_dict(self) -> Dict:
        return {
            "user_id": self._user_id,
            "username": self._username,
            "hashed_password": self._hashed_password,
            "salt": self._salt,
            "registration_date": self._registration_date.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'User':
        registration_date = datetime.fromisoformat(data["registration_date"])
        
        user = cls.__new__(cls)
        user._user_id = data["user_id"]
        user._username = data["username"]
        user._salt = data["salt"]
        user._hashed_password = data["hashed_password"]
        user._registration_date = registration_date
        return user
