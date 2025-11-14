"""Вспомогательные функции и валидаторы."""
import json
import os
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from .currencies import CurrencyRegistry, CurrencyNotFoundError
from .exceptions import InvalidCurrencyCodeError, InvalidAmountError


def load_json(file_path: str) -> Any:
    """Загрузка данных из JSON файла."""
    if not os.path.exists(file_path):
        # Возвращаем пустые данные по умолчанию
        if 'users' in file_path:
            return []
        elif 'portfolios' in file_path:
            return []
        else:
            return {}
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:  # Если файл пустой
                if 'users' in file_path:
                    return []
                elif 'portfolios' in file_path:
                    return []
                else:
                    return {}
            return json.loads(content)
    except (json.JSONDecodeError, Exception):
        # Если файл поврежден, возвращаем данные по умолчанию
        if 'users' in file_path:
            return []
        elif 'portfolios' in file_path:
            return []
        else:
            return {}


def save_json(data: Any, file_path: str) -> None:
    """Сохранение данных в JSON файл."""
    # Создаем директорию если не существует
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def validate_currency_code_format(code: str) -> Tuple[bool, Optional[str]]:
    """Базовая валидация формата кода валюты.
    
    Args:
        code: Код валюты для проверки
        
    Returns:
        Tuple[bool, Optional[str]]: (валиден ли формат, сообщение об ошибке)
    """
    if not isinstance(code, str):
        return False, "Код валюты должен быть строкой"
    
    if len(code) < 2 or len(code) > 5:
        return False, "Длина кода валюты должна быть от 2 до 5 символов"
    
    if not code.isalnum():
        return False, "Код валюты должен содержать только буквы и цифры"
    
    if ' ' in code:
        return False, "Код валюты не должен содержать пробелы"
    
    if not code.isupper():
        return False, "Код валюты должен быть в верхнем регистре"
    
    return True, None


def validate_currency_code_exists(code: str) -> Tuple[bool, Optional[str]]:
    """Проверка существования валюты в реестре.
    
    Args:
        code: Код валюты для проверки
        
    Returns:
        Tuple[bool, Optional[str]]: (существует ли валюта, сообщение об ошибке)
    """
    try:
        CurrencyRegistry.get_currency(code)
        return True, None
    except CurrencyNotFoundError:
        return False, f"Валюта '{code}' не найдена в реестре"
    except Exception as e:
        return False, f"Ошибка при проверке валюты '{code}': {e}"


def validate_currency_code(code: str) -> bool:
    """Проверка корректности кода валюты через иерархию валют.
    
    Args:
        code: Код валюты для проверки
        
    Returns:
        bool: True если валюта валидна
    """
    format_valid, format_error = validate_currency_code_format(code)
    if not format_valid:
        return False
    
    exists_valid, exists_error = validate_currency_code_exists(code)
    return exists_valid


def validate_currency_pair(from_currency: str, to_currency: str) -> Tuple[bool, Optional[str]]:
    """Валидация валютной пары.
    
    Args:
        from_currency: Исходная валюта
        to_currency: Целевая валюта
        
    Returns:
        Tuple[bool, Optional[str]]: (валидна ли пара, сообщение об ошибке)
    """
    # Проверяем исходную валюту
    format_valid, format_error = validate_currency_code_format(from_currency)
    if not format_valid:
        return False, f"Неверный формат исходной валюты: {format_error}"
    
    exists_valid, exists_error = validate_currency_code_exists(from_currency)
    if not exists_valid:
        return False, f"Исходная валюта не найдена: {exists_error}"
    
    # Проверяем целевую валюту
    format_valid, format_error = validate_currency_code_format(to_currency)
    if not format_valid:
        return False, f"Неверный формат целевой валюты: {format_error}"
    
    exists_valid, exists_error = validate_currency_code_exists(to_currency)
    if not exists_valid:
        return False, f"Целевая валюта не найдена: {exists_error}"
    
    # Проверяем что это не одна и та же валюта
    if from_currency == to_currency:
        return False, "Исходная и целевая валюта не могут быть одинаковыми"
    
    return True, None


def validate_currency_amount(currency_code: str, amount: float) -> Tuple[bool, Optional[str]]:
    """Расширенная валидация суммы для конкретной валюты.
    
    Args:
        currency_code: Код валюты
        amount: Сумма для проверки
        
    Returns:
        Tuple[bool, Optional[str]]: (валидна ли сумма, сообщение об ошибке)
    """
    # Сначала проверяем валюту
    currency_valid, currency_error = validate_currency_code_exists(currency_code)
    if not currency_valid:
        return False, currency_error
    
    # Проверяем сумму
    if not isinstance(amount, (int, float)):
        return False, "Сумма должна быть числом"
    
    if amount <= 0:
        return False, "Сумма должна быть положительной"
    
    # Проверка для криптовалют (обычно требуют больше знаков после запятой)
    try:
        currency = CurrencyRegistry.get_currency(currency_code)
        if hasattr(currency, 'market_cap'):  # Это криптовалюта
            if amount < 0.00000001:  # Минимальная сумма для BTC-like валют (1 satoshi)
                return False, "Сумма слишком мала для данной криптовалюты"
            
            # Проверка максимальной суммы для криптовалют (условно)
            if amount > 10000:  # Пример бизнес-правила
                return False, "Сумма слишком велика для одной операции"
        
        else:  # Фиатная валюта
            if amount < 0.01:  # Минимальная сумма для фиатных валют
                return False, "Сумма слишком мала для данной валюты"
            
            if amount > 1000000:  # Пример бизнес-правила
                return False, "Сумма слишком велика для одной операции"
    
    except Exception:
        pass  # Игнорируем ошибки при дополнительных проверках
    
    return True, None


def validate_amount(amount: float) -> bool:
    """Базовая проверка что сумма положительная.
    
    Args:
        amount: Сумма для проверки
        
    Returns:
        bool: True если сумма валидна
    """
    return isinstance(amount, (int, float)) and amount > 0


def format_amount(amount: float, currency_code: str = "") -> str:
    """Форматирование суммы с учетом типа валюты.
    
    Args:
        amount: Сумма для форматирования
        currency_code: Код валюты для определения формата
        
    Returns:
        str: Отформатированная строка суммы
    """
    try:
        if currency_code:
            currency = CurrencyRegistry.get_currency(currency_code)
            if hasattr(currency, 'market_cap'):  # Криптовалюта
                # Для криптовалют показываем больше знаков после запятой
                if amount < 0.001:
                    return f"{amount:.8f}"
                elif amount < 1:
                    return f"{amount:.6f}"
                else:
                    return f"{amount:.4f}"
            else:  # Фиатная валюта
                return f"{amount:.2f}"
        else:
            # Без указания валюты используем общий формат
            return f"{amount:.2f}"
    except CurrencyNotFoundError:
        return f"{amount:.2f}"


def parse_currency_pair(pair: str) -> Optional[Tuple[str, str]]:
    """Парсинг валютной пары вида 'EUR_USD'.
    
    Args:
        pair: Строка валютной пары
        
    Returns:
        Optional[Tuple[str, str]]: Кортеж (from_currency, to_currency) или None
    """
    if '_' not in pair:
        return None
    
    parts = pair.split('_')
    if len(parts) != 2:
        return None
    
    from_currency, to_currency = parts[0].upper(), parts[1].upper()
    
    # Проверяем валидность обеих валют
    if not validate_currency_code(from_currency) or not validate_currency_code(to_currency):
        return None
    
    return from_currency, to_currency


def is_rate_fresh(updated_at: str, max_age_minutes: int = 5) -> bool:
    """Проверка свежести курса валюты.
    
    Args:
        updated_at: Время обновления в ISO формате
        max_age_minutes: Максимальный возраст в минутах
        
    Returns:
        bool: True если курс свежий
    """
    try:
        updated_time = datetime.fromisoformat(updated_at)
        current_time = datetime.now()
        age = current_time - updated_time
        return age < timedelta(minutes=max_age_minutes)
    except (ValueError, TypeError):
        return False


def format_datetime(dt_string: str) -> str:
    """Форматирование даты и времени для вывода.
    
    Args:
        dt_string: Строка даты-времени в ISO формате
        
    Returns:
        str: Отформатированная строка даты-времени
    """
    try:
        dt = datetime.fromisoformat(dt_string)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return dt_string


def convert_currency_amount(amount: float, from_currency: str, to_currency: str, 
                           exchange_rate: float) -> float:
    """Конвертация суммы из одной валюты в другую.
    
    Args:
        amount: Исходная сумма
        from_currency: Исходная валюта
        to_currency: Целевая валюта
        exchange_rate: Курс обмена
        
    Returns:
        float: Сконвертированная сумма
        
    Raises:
        ValueError: Если параметры невалидны
    """
    # Валидация входных параметров
    amount_valid, amount_error = validate_currency_amount(from_currency, amount)
    if not amount_valid:
        raise ValueError(f"Неверная сумма для конвертации: {amount_error}")
    
    pair_valid, pair_error = validate_currency_pair(from_currency, to_currency)
    if not pair_valid:
        raise ValueError(f"Неверная валютная пара: {pair_error}")
    
    if exchange_rate <= 0:
        raise ValueError("Курс обмена должен быть положительным")
    
    # Выполняем конвертацию
    converted_amount = amount * exchange_rate
    
    return converted_amount


def convert_currency_amount_with_rounding(amount: float, from_currency: str, to_currency: str, 
                                         exchange_rate: float, decimal_places: int = None) -> float:
    """Конвертация суммы с округлением до указанного количества знаков.
    
    Args:
        amount: Исходная сумма
        from_currency: Исходная валюта
        to_currency: Целевая валюта
        exchange_rate: Курс обмена
        decimal_places: Количество знаков после запятой (авто если None)
        
    Returns:
        float: Сконвертированная и округленная сумма
    """
    converted_amount = convert_currency_amount(amount, from_currency, to_currency, exchange_rate)
    
    if decimal_places is None:
        # Автоматическое определение количества знаков на основе типа валюты
        try:
            currency = CurrencyRegistry.get_currency(to_currency)
            if hasattr(currency, 'market_cap'):  # Криптовалюта
                decimal_places = 8
            else:  # Фиатная валюта
                decimal_places = 2
        except CurrencyNotFoundError:
            decimal_places = 2
    
    return round(converted_amount, decimal_places)


def calculate_portfolio_value(portfolio_balances: Dict[str, float], 
                             exchange_rates: Dict[str, float], 
                             base_currency: str = 'USD') -> float:
    """Расчет общей стоимости портфеля в базовой валюте.
    
    Args:
        portfolio_balances: Балансы портфеля {валюта: сумма}
        exchange_rates: Курсы обмена {валюта: курс к USD}
        base_currency: Базовая валюта для расчета
        
    Returns:
        float: Общая стоимость портфеля в базовой валюте
    """
    total_value = 0.0
    
    # Валидация базовой валюты
    if not validate_currency_code(base_currency):
        raise ValueError(f"Неизвестная базовая валюта: {base_currency}")
    
    for currency, balance in portfolio_balances.items():
        # Валидация валюты из портфеля
        if not validate_currency_code(currency):
            continue  # Пропускаем неизвестные валюты
        
        if currency == base_currency:
            total_value += balance
        elif currency in exchange_rates:
            # Конвертируем через USD
            rate_to_usd = exchange_rates[currency]
            if base_currency in exchange_rates:
                rate_from_usd_to_base = exchange_rates[base_currency]
                value_in_base = (balance / rate_to_usd) * rate_from_usd_to_base
                total_value += value_in_base
    
    return round(total_value, 2)  # Округляем до 2 знаков для денег


def calculate_conversion_fee(amount: float, fee_percent: float = 0.1) -> float:
    """Расчет комиссии за конвертацию.
    
    Args:
        amount: Сумма конвертации
        fee_percent: Процент комиссии
        
    Returns:
        float: Сумма комиссии
    """
    if amount <= 0:
        return 0.0
    
    if fee_percent < 0 or fee_percent > 100:
        raise ValueError("Процент комиссии должен быть между 0 и 100")
    
    fee = amount * (fee_percent / 100)
    return round(fee, 2)


def calculate_net_amount_after_fee(amount: float, fee_percent: float = 0.1) -> Tuple[float, float]:
    """Расчет чистой суммы после вычета комиссии.
    
    Args:
        amount: Исходная сумма
        fee_percent: Процент комиссии
        
    Returns:
        Tuple[float, float]: (чистая сумма, комиссия)
    """
    fee = calculate_conversion_fee(amount, fee_percent)
    net_amount = amount - fee
    return round(net_amount, 2), fee


def validate_username(username: str) -> Tuple[bool, Optional[str]]:
    """Валидация имени пользователя.
    
    Args:
        username: Имя пользователя для проверки
        
    Returns:
        Tuple[bool, Optional[str]]: (валидно ли имя, сообщение об ошибке)
    """
    if not username or not username.strip():
        return False, "Имя пользователя не может быть пустым"
    
    if len(username) < 3:
        return False, "Имя пользователя должно содержать не менее 3 символов"
    
    if len(username) > 50:
        return False, "Имя пользователя должно содержать не более 50 символов"
    
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return False, "Имя пользователя может содержать только буквы, цифры и подчеркивания"
    
    # Запрещенные имена
    forbidden_names = ['admin', 'root', 'system', 'administrator']
    if username.lower() in forbidden_names:
        return False, "Это имя пользователя запрещено"
    
    return True, None


def validate_password(password: str) -> Tuple[bool, Optional[str]]:
    """Валидация пароля.
    
    Args:
        password: Пароль для проверки
        
    Returns:
        Tuple[bool, Optional[str]]: (валиден ли пароль, сообщение об ошибке)
    """
    if not password:
        return False, "Пароль не может быть пустым"
    
    if len(password) < 4:
        return False, "Пароль должен содержать не менее 4 символов"
    
    if len(password) > 100:
        return False, "Пароль должен содержать не более 100 символов"
    
    # Дополнительные проверки безопасности
    if password.lower() == 'password':
        return False, "Пароль слишком простой"
    
    if username and password.lower() == username.lower():
        return False, "Пароль не должен совпадать с именем пользователя"
    
    return True, None


def generate_currency_pairs(base_currency: str = 'USD') -> List[Tuple[str, str]]:
    """Генерация списка возможных валютных пар.
    
    Args:
        base_currency: Базовая валюта
        
    Returns:
        List[Tuple[str, str]]: Список валютных пар
    """
    if not validate_currency_code(base_currency):
        return []
    
    pairs = []
    supported_currencies = CurrencyRegistry.get_supported_currencies()
    
    for currency_code in supported_currencies.keys():
        if currency_code != base_currency:
            pairs.append((base_currency, currency_code))
            pairs.append((currency_code, base_currency))
    
    return pairs


def normalize_currency_code(code: str) -> str:
    """Нормализация кода валюты.
    
    Args:
        code: Код валюты для нормализации
        
    Returns:
        str: Нормализованный код валюты
    """
    if not code:
        return code
    
    # Приводим к верхнему регистру и удаляем пробелы
    normalized = code.upper().strip()
    
    # Удаляем неалфавитные символы (кроме цифр)
    normalized = ''.join(c for c in normalized if c.isalnum())
    
    return normalized
