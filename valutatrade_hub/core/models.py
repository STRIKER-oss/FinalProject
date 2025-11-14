"""Модели данных для валютного кошелька."""
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from .exceptions import InsufficientFundsError, InvalidAmountError
from .currencies import get_currency


class Wallet:
    """Класс кошелька пользователя для одной конкретной валюты."""
    
    def __init__(self, currency_code: str, balance: float = 0.0):
        # Приватные поля
        self._currency_code = currency_code.upper()
        self._balance = float(balance)
        
        # Точка интеграции: валидация при создании
        self._validate_initial_state()
    
    def _validate_initial_state(self) -> None:
        """Валидация начального состояния кошелька.
        
        Точка интеграции для дополнительной бизнес-логики валидации.
        """
        # Валидация кода валюты через иерархию валют
        try:
            currency_obj = get_currency(self._currency_code)
            # Точка интеграции: можно добавить логирование создания кошелька
        except Exception as e:
            raise ValueError(f"Неверный код валюты: {self._currency_code}") from e
        
        # Валидация баланса
        if self._balance < 0:
            raise ValueError("Начальный баланс не может быть отрицательным")
        
        # Точка интеграции: можно добачить проверки для конкретных типов валют
        if hasattr(currency_obj, 'market_cap'):  # Криптовалюта
            if self._balance > 1000000:  # Пример бизнес-правила
                # Точка интеграции для аудита больших сумм
                pass
    
    @property
    def currency_code(self) -> str:
        """Геттер для кода валюты."""
        return self._currency_code
    
    @property
    def balance(self) -> float:
        """Геттер для баланса."""
        return self._balance
    
    @balance.setter
    def balance(self, value: float) -> None:
        """Сеттер для баланса с валидацией.
        
        Точка интеграции для контроля изменений баланса.
        """
        if not isinstance(value, (int, float)):
            raise ValueError("Баланс должен быть числом")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным")
        
        old_balance = self._balance
        self._balance = float(value)
        
        # Точка интеграции: можно добавить логирование изменений баланса
        # или уведомления о значительных изменениях
    
    def deposit(self, amount: float) -> None:
        """Пополнение баланса.
        
        Args:
            amount: Сумма для пополнения
            
        Raises:
            InvalidAmountError: Если сумма невалидна
        """
        # Точка интеграции: предварительная валидация
        if not isinstance(amount, (int, float)):
            raise InvalidAmountError(amount)
        if amount <= 0:
            raise InvalidAmountError(amount)
        
        old_balance = self._balance
        self._balance += amount
        
        # Точка интеграции: логирование операции пополнения
        # или вызов хуков для внешних систем
    
    def withdraw(self, amount: float) -> bool:
        """Снятие средств (если баланс позволяет).
        
        Args:
            amount: Сумма для снятия
            
        Returns:
            bool: True если операция успешна
            
        Raises:
            InvalidAmountError: Если сумма невалидна
            InsufficientFundsError: Если недостаточно средств
        """
        # Точка интеграции: предварительная валидация
        if not isinstance(amount, (int, float)):
            raise InvalidAmountError(amount)
        if amount <= 0:
            raise InvalidAmountError(amount)
        
        # Проверяем достаточно ли средств
        if amount > self._balance:
            raise InsufficientFundsError(
                currency_code=self._currency_code,
                available=self._balance,
                required=amount
            )
        
        old_balance = self._balance
        self._balance -= amount
        
        # Точка интеграции: логирование операции снятия
        # или вызов хуков для внешних систем
        
        return True
    
    def get_balance_info(self) -> Dict[str, str]:
        """Вывод информации о текущем балансе.
        
        Returns:
            Dict с информацией о балансе
        """
        return {
            "currency_code": self._currency_code,
            "balance": f"{self._balance:.2f}",
            "balance_raw": self._balance
        }
    
    def to_dict(self) -> Dict:
        """Преобразование в словарь для сохранения.
        
        Точка интеграции для сериализации.
        """
        return {
            "currency_code": self._currency_code,
            "balance": self._balance
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Wallet':
        """Создание кошелька из словаря.
        
        Точка интеграции для десериализации.
        """
        return cls(
            currency_code=data["currency_code"],
            balance=data["balance"]
        )


class Portfolio:
    """Класс управления всеми кошельками одного пользователя."""
    
    def __init__(self, user_id: int, user: Optional['User'] = None):
        # Приватные поля
        self._user_id = user_id
        self._user = user
        self._wallets: Dict[str, Wallet] = {}
        
        # Точка интеграции: инициализация портфеля
        self._initialize_portfolio()
    
    def _initialize_portfolio(self) -> None:
        """Инициализация портфеля.
        
        Точка интеграции для начальной настройки портфеля.
        """
        # Можно добавить создание кошельков по умолчанию
        # или загрузку начальных данных из конфигурации
        pass
    
    @property
    def user_id(self) -> int:
        """Геттер для ID пользователя."""
        return self._user_id
    
    @property
    def user(self) -> Optional['User']:
        """Геттер для объекта пользователя (без возможности перезаписи)."""
        return self._user
    
    @property
    def wallets(self) -> Dict[str, Wallet]:
        """Геттер, который возвращает копию словаря кошельков."""
        return self._wallets.copy()
    
    def get_balance(self, currency_code: str) -> float:
        """Получение баланса по валюте.
        
        Args:
            currency_code: Код валюты
            
        Returns:
            float: Текущий баланс
        """
        wallet = self.get_wallet(currency_code)
        return wallet.balance if wallet else 0.0
    
    def add_currency(self, currency_code: str, initial_balance: float = 0.0) -> bool:
        """Добавляет новый кошелёк в портфель (если его ещё нет).
        
        Args:
            currency_code: Код валюты
            initial_balance: Начальный баланс
            
        Returns:
            bool: True если кошелек создан, False если уже существует
        """
        currency_code = currency_code.upper()
        if currency_code in self._wallets:
            return False  # Кошелёк уже существует
        
        # Точка интеграции: создание кошелька
        wallet = Wallet(currency_code, initial_balance)
        self._wallets[currency_code] = wallet
        
        # Точка интеграции: логирование создания кошелька
        return True
    
    def get_wallet(self, currency_code: str) -> Optional[Wallet]:
        """Возвращает объект Wallet по коду валюты.
        
        Args:
            currency_code: Код валюты
            
        Returns:
            Optional[Wallet]: Объект кошелька или None
        """
        return self._wallets.get(currency_code.upper())
    
    def get_total_value(self, exchange_rates: Dict[str, float], base_currency: str = 'USD') -> float:
        """Возвращает общую стоимость всех валют пользователя в указанной базовой валюте.
        
        Args:
            exchange_rates: Словарь курсов валют
            base_currency: Базовая валюта для расчета
            
        Returns:
            float: Общая стоимость портфеля
        """
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
        """Пополнение конкретного кошелька.
        
        Args:
            currency_code: Код валюты
            amount: Сумма пополнения
            
        Returns:
            bool: True если операция успешна
        """
        wallet = self.get_wallet(currency_code)
        if not wallet:
            # Если кошелька нет - создаем его
            self.add_currency(currency_code, 0.0)
            wallet = self.get_wallet(currency_code)
        
        try:
            wallet.deposit(amount)
            return True
        except (ValueError, InvalidAmountError):
            return False
    
    def withdraw_from_wallet(self, currency_code: str, amount: float) -> bool:
        """Снятие средств с конкретного кошелька.
        
        Args:
            currency_code: Код валюты
            amount: Сумма снятия
            
        Returns:
            bool: True если операция успешна
        """
        wallet = self.get_wallet(currency_code)
        if not wallet:
            return False
        
        return wallet.withdraw(amount)
    
    def buy_currency(self, from_currency: str, to_currency: str, amount: float, 
                    exchange_rate: float) -> bool:
        """Покупка валюты (списание с USD-кошелька, начисление на целевой кошелёк).
        
        Args:
            from_currency: Исходная валюта (обычно USD)
            to_currency: Целевая валюта
            amount: Количество покупаемой валюты
            exchange_rate: Курс обмена
            
        Returns:
            bool: True если операция успешна
        """
        # Рассчитываем стоимость покупки в USD
        cost_in_usd = amount * exchange_rate
        
        # Проверяем достаточно ли средств в USD кошельке
        usd_wallet = self.get_wallet(from_currency)
        if not usd_wallet or usd_wallet.balance < cost_in_usd:
            return False
        
        # Списываем средства с USD кошелька
        if not usd_wallet.withdraw(cost_in_usd):
            return False
        
        # Добавляем или пополняем целевой кошелёк
        target_wallet = self.get_wallet(to_currency)
        if target_wallet:
            target_wallet.deposit(amount)
        else:
            self.add_currency(to_currency, amount)
        
        # Точка интеграции: логирование успешной покупки
        return True
    
    def sell_currency(self, from_currency: str, to_currency: str, amount: float,
                     exchange_rate: float) -> bool:
        """Продажа валюты (списание с исходного кошелька, начисление на USD-кошелёк).
        
        Args:
            from_currency: Исходная валюта
            to_currency: Целевая валюта (обычно USD)
            amount: Количество продаваемой валюты
            exchange_rate: Курс обмена
            
        Returns:
            bool: True если операция успешна
        """
        # Проверяем достаточно ли средств в исходном кошельке
        from_wallet = self.get_wallet(from_currency)
        if not from_wallet or from_wallet.balance < amount:
            return False
        
        # Рассчитываем выручку в USD
        revenue_in_usd = amount * exchange_rate
        
        # Списываем средства с исходного кошелька
        if not from_wallet.withdraw(amount):
            return False
        
        # Добавляем или пополняем USD кошелёк
        usd_wallet = self.get_wallet(to_currency)
        if usd_wallet:
            usd_wallet.deposit(revenue_in_usd)
        else:
            self.add_currency(to_currency, revenue_in_usd)
        
        # Точка интеграции: логирование успешной продажи
        return True
    
    def get_all_balances(self) -> Dict[str, float]:
        """Возвращает словарь со всеми балансами.
        
        Returns:
            Dict[str, float]: Словарь балансов {валюта: баланс}
        """
        return {code: wallet.balance for code, wallet in self._wallets.items()}
    
    def to_dict(self) -> Dict:
        """Преобразование в словарь для сохранения.
        
        Точка интеграции для сериализации портфеля.
        """
        return {
            "user_id": self._user_id,
            "wallets": {code: wallet.to_dict() for code, wallet in self._wallets.items()}
        }
    
    @classmethod
    def from_dict(cls, data: Dict, user: Optional['User'] = None) -> 'Portfolio':
        """Создание портфеля из словаря.
        
        Точка интеграции для десериализации портфеля.
        """
        portfolio = cls(user_id=data["user_id"], user=user)
        for code, wallet_data in data.get("wallets", {}).items():
            portfolio._wallets[code] = Wallet.from_dict(wallet_data)
        return portfolio


class User:
    """Класс пользователя системы."""
    
    def __init__(self, user_id: int, username: str, password: str, 
                 salt: Optional[str] = None, registration_date: Optional[datetime] = None):
        # Приватные поля
        self._user_id = user_id
        self._username = username.strip()
        self._salt = salt or self._generate_salt()
        self._hashed_password = self._hash_password(password, self._salt)
        self._registration_date = registration_date or datetime.now()
        
        # Точка интеграции: валидация при создании пользователя
        self._validate_initial_state(password)
    
    def _validate_initial_state(self, password: str) -> None:
        """Валидация начального состояния пользователя.
        
        Точка интеграции для бизнес-правил создания пользователя.
        """
        if not self._username:
            raise ValueError("Имя пользователя не может быть пустым")
        
        if len(self._username) < 3:
            raise ValueError("Имя пользователя должно содержать не менее 3 символов")
        
        if len(password) < 4:
            raise ValueError("Пароль должен содержать не менее 4 символов")
        
        # Точка интеграции: можно добачить проверку запрещенных имен
        forbidden_names = ['admin', 'root', 'system']
        if self._username.lower() in forbidden_names:
            raise ValueError("Это имя пользователя запрещено")
    
    @property
    def user_id(self) -> int:
        """Геттер для ID пользователя."""
        return self._user_id
    
    @user_id.setter
    def user_id(self, value: int) -> None:
        """Сеттер для ID пользователя.
        
        Точка интеграции для контроля изменений ID.
        """
        if not isinstance(value, int) or value <= 0:
            raise ValueError("ID пользователя должен быть положительным целым числом")
        
        old_id = self._user_id
        self._user_id = value
        
        # Точка интеграции: логирование изменения ID
        # или обновление связанных данных
    
    @property
    def username(self) -> str:
        """Геттер для имени пользователя."""
        return self._username
    
    @username.setter
    def username(self, value: str) -> None:
        """Сеттер для имени пользователя.
        
        Точка интеграции для контроля изменений имени.
        """
        if not value or not value.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        
        old_username = self._username
        self._username = value.strip()
        
        # Точка интеграции: логирование изменения имени
        # или обновление в связанных системах
    
    @property
    def hashed_password(self) -> str:
        """Геттер для хешированного пароля."""
        return self._hashed_password
    
    @property
    def salt(self) -> str:
        """Геттер для соли."""
        return self._salt
    
    @property
    def registration_date(self) -> datetime:
        """Геттер для даты регистрации."""
        return self._registration_date
    
    def _generate_salt(self) -> str:
        """Генерация уникальной соли.
        
        Точка интеграции для изменения алгоритма генерации соли.
        """
        return hashlib.sha256(str(datetime.now().timestamp()).encode()).hexdigest()[:8]
    
    def _hash_password(self, password: str, salt: str) -> str:
        """Хеширование пароля с солью.
        
        Точка интеграции для изменения алгоритма хеширования.
        """
        if len(password) < 4:
            raise ValueError("Пароль должен содержать не менее 4 символов")
        
        return hashlib.sha256((password + salt).encode()).hexdigest()
    
    def get_user_info(self) -> Dict[str, str]:
        """Выводит информацию о пользователе (без пароля).
        
        Returns:
            Dict с информацией о пользователе
        """
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat()
        }
    
    def change_password(self, new_password: str) -> None:
        """Изменяет пароль пользователя.
        
        Args:
            new_password: Новый пароль
            
        Raises:
            ValueError: Если пароль невалиден
        """
        if len(new_password) < 4:
            raise ValueError("Пароль должен содержать не менее 4 символов")
        
        # Генерируем новую соль для дополнительной безопасности
        old_salt = self._salt
        self._salt = self._generate_salt()
        self._hashed_password = self._hash_password(new_password, self._salt)
        
        # Точка интеграции: логирование смены пароля
        # или уведомление пользователя
    
    def verify_password(self, password: str) -> bool:
        """Проверяет введённый пароль на совпадение.
        
        Args:
            password: Пароль для проверки
            
        Returns:
            bool: True если пароль верный
        """
        hashed_input = self._hash_password(password, self._salt)
        
        # Точка интеграции: можно добавить логирование попыток входа
        # или систему блокировки при множественных неудачных попытках
        
        return hashed_input == self._hashed_password
    
    def to_dict(self) -> Dict:
        """Преобразование в словарь для сохранения в JSON.
        
        Точка интеграции для сериализации пользователя.
        """
        return {
            "user_id": self._user_id,
            "username": self._username,
            "hashed_password": self._hashed_password,
            "salt": self._salt,
            "registration_date": self._registration_date.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'User':
        """Создание пользователя из словаря.
        
        Точка интеграции для десериализации пользователя.
        """
        registration_date = datetime.fromisoformat(data["registration_date"])
        
        # Создаем объект без вызова конструктора (чтобы избежать валидации пароля)
        user = cls.__new__(cls)
        user._user_id = data["user_id"]
        user._username = data["username"]
        user._salt = data["salt"]
        user._hashed_password = data["hashed_password"]
        user._registration_date = registration_date
        return user
