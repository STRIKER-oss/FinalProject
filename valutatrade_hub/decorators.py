"""Декораторы для приложения Valutatrade Hub."""
import functools
import logging
from typing import Any, Callable, Dict, Optional, Union
from .core.exceptions import ValutatradeError


def log_action(action: str, verbose: bool = False):
    """Декоратор для логирования доменных операций.
    
    Args:
        action: Название действия (BUY/SELL/REGISTER/LOGIN и т.д.)
        verbose: Подробное логирование с контекстом
    
    Returns:
        Декорированная функция
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            logger = logging.getLogger("valutatrade.actions")
            
            # Подготавливаем базовые поля для лога
            log_fields = {
                "action": action,
                "result": "OK"
            }
            
            try:
                # Извлекаем информацию из аргументов для логирования
                _extract_log_fields(log_fields, args, kwargs, action)
                
                # Выполняем оригинальную функцию
                result = func(*args, **kwargs)
                
                # Добавляем дополнительную информацию при успехе
                if verbose and hasattr(result, '__dict__'):
                    log_fields["context"] = _get_verbose_context(result, action)
                
                # Логируем успешное выполнение
                _log_action(logger, log_fields)
                
                return result
                
            except ValutatradeError as e:
                # Логируем бизнес-ошибки
                log_fields.update({
                    "result": "ERROR",
                    "error_type": e.__class__.__name__,
                    "error_message": str(e)
                })
                _log_action(logger, log_fields, level=logging.WARNING)
                raise
                
            except Exception as e:
                # Логируем непредвиденные ошибки
                log_fields.update({
                    "result": "ERROR", 
                    "error_type": "UnexpectedError",
                    "error_message": str(e)
                })
                _log_action(logger, log_fields, level=logging.ERROR)
                raise
        
        return wrapper
    return decorator


def _extract_log_fields(log_fields: Dict[str, Any], args: tuple, kwargs: dict, action: str) -> None:
    """Извлечение полей для логирования из аргументов функции."""
    # Для методов классов первый аргумент - self
    if args and hasattr(args[0], '__class__'):
        # Пытаемся извлечь user_id или username из self если это менеджер
        manager_instance = args[0]
        if hasattr(manager_instance, 'current_user') and manager_instance.current_user:
            log_fields["username"] = manager_instance.current_user.username
            log_fields["user_id"] = manager_instance.current_user.user_id
        elif hasattr(manager_instance, 'user_manager') and manager_instance.user_manager:
            # Для PortfolioManager
            pass
    
    # Извлекаем параметры из kwargs
    param_mappings = {
        'username': 'username',
        'user_id': 'user_id', 
        'currency': 'currency_code',
        'currency_code': 'currency_code',
        'from_currency': 'from_currency',
        'to_currency': 'to_currency',
        'amount': 'amount',
        'rate': 'rate',
        'exchange_rate': 'rate',
        'base_currency': 'base_currency'
    }
    
    for param_name, log_field in param_mappings.items():
        if param_name in kwargs and kwargs[param_name] is not None:
            # Преобразуем amount в float для корректного форматирования
            if param_name == 'amount' and isinstance(kwargs[param_name], str):
                try:
                    log_fields[log_field] = float(kwargs[param_name])
                except (ValueError, TypeError):
                    log_fields[log_field] = kwargs[param_name]
            else:
                log_fields[log_field] = kwargs[param_name]
    
    # Для методов с определенной сигнатурой
    if action in ["BUY", "SELL"] and len(args) >= 3:
        # buy_currency(self, currency, amount) или sell_currency(self, currency, amount)
        if len(args) >= 3:
            if 'currency_code' not in log_fields:
                log_fields['currency_code'] = args[1]  # currency
            if 'amount' not in log_fields:
                amount_arg = args[2]  # amount
                # Преобразуем amount в float для корректного форматирования
                if isinstance(amount_arg, str):
                    try:
                        log_fields['amount'] = float(amount_arg)
                    except (ValueError, TypeError):
                        log_fields['amount'] = amount_arg
                else:
                    log_fields['amount'] = amount_arg


def _get_verbose_context(result: Any, action: str) -> Dict[str, Any]:
    """Получение контекста для подробного логирования."""
    context = {}
    
    if action in ["BUY", "SELL"] and hasattr(result, '__dict__'):
        # Можно добавить информацию о состоянии портфеля
        context["operation_result"] = "completed"
    
    return context


def _log_action(logger: logging.Logger, fields: Dict[str, Any], level: int = logging.INFO) -> None:
    """Логирование действия с дополнительными полями."""
    log_record = logger.makeRecord(
        name=logger.name,
        level=level,
        fn="",
        lno=0,
        msg="",  # Сообщение будет сформировано форматтером
        args=(),
        exc_info=None
    )
    
    # Добавляем дополнительные поля
    for field, value in fields.items():
        setattr(log_record, field, value)
    
    logger.handle(log_record)
