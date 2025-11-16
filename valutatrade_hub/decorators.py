"""Декораторы для приложения Valutatrade Hub."""
import functools
import logging
from typing import Any, Callable, Dict
from .core.exceptions import ValutatradeError


def log_action(action: str, verbose: bool = False):
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            logger = logging.getLogger("valutatrade.actions")
            
            log_fields = {
                "action": action,
                "result": "OK"
            }
            
            try:
                _extract_log_fields(log_fields, args, kwargs, action)
                
                result = func(*args, **kwargs)
                
                if verbose and hasattr(result, '__dict__'):
                    log_fields["context"] = _get_verbose_context(result, action)
                
                _log_action(logger, log_fields)
                
                return result
                
            except ValutatradeError as e:
                log_fields.update({
                    "result": "ERROR",
                    "error_type": e.__class__.__name__,
                    "error_message": str(e)
                })
                _log_action(logger, log_fields, level=logging.WARNING)
                raise
                
            except Exception as e:
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
    if args and hasattr(args[0], '__class__'):
        manager_instance = args[0]
        if hasattr(manager_instance, 'current_user') and manager_instance.current_user:
            log_fields["username"] = manager_instance.current_user.username
            log_fields["user_id"] = manager_instance.current_user.user_id
        elif hasattr(manager_instance, 'user_manager') and manager_instance.user_manager:
            pass
    
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
            if param_name == 'amount' and isinstance(kwargs[param_name], str):
                try:
                    log_fields[log_field] = float(kwargs[param_name])
                except (ValueError, TypeError):
                    log_fields[log_field] = kwargs[param_name]
            else:
                log_fields[log_field] = kwargs[param_name]
    
    if action in ["BUY", "SELL"] and len(args) >= 3:
        if len(args) >= 3:
            if 'currency_code' not in log_fields:
                log_fields['currency_code'] = args[1]
            if 'amount' not in log_fields:
                amount_arg = args[2]
                if isinstance(amount_arg, str):
                    try:
                        log_fields['amount'] = float(amount_arg)
                    except (ValueError, TypeError):
                        log_fields['amount'] = amount_arg
                else:
                    log_fields['amount'] = amount_arg


def _get_verbose_context(result: Any, action: str) -> Dict[str, Any]:
    context = {}
    
    if action in ["BUY", "SELL"] and hasattr(result, '__dict__'):
        context["operation_result"] = "completed"
    
    return context


def _log_action(logger: logging.Logger, fields: Dict[str, Any], level: int = logging.INFO) -> None:
    log_record = logger.makeRecord(
        name=logger.name,
        level=level,
        fn="",
        lno=0,
        msg="",
        args=(),
        exc_info=None
    )
    
    for field, value in fields.items():
        setattr(log_record, field, value)
    
    logger.handle(log_record)
