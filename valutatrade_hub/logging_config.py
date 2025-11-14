"""Настройка логирования для приложения Valutatrade Hub."""
import logging
import logging.handlers
import os
import json
from datetime import datetime
from typing import Dict, Any
from .infra.settings import settings


class JSONFormatter(logging.Formatter):
    """Форматтер для JSON логов."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Форматирование записи лога в JSON."""
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Добавляем дополнительные поля если они есть
        if hasattr(record, 'action'):
            log_entry["action"] = record.action
        if hasattr(record, 'username'):
            log_entry["username"] = record.username
        if hasattr(record, 'user_id'):
            log_entry["user_id"] = record.user_id
        if hasattr(record, 'currency_code'):
            log_entry["currency_code"] = record.currency_code
        if hasattr(record, 'amount'):
            # Безопасное форматирование amount
            try:
                log_entry["amount"] = float(record.amount)
            except (ValueError, TypeError):
                log_entry["amount"] = record.amount
        if hasattr(record, 'rate'):
            log_entry["rate"] = record.rate
        if hasattr(record, 'base_currency'):
            log_entry["base_currency"] = record.base_currency
        if hasattr(record, 'result'):
            log_entry["result"] = record.result
        if hasattr(record, 'error_type'):
            log_entry["error_type"] = record.error_type
        if hasattr(record, 'error_message'):
            log_entry["error_message"] = record.error_message
        if hasattr(record, 'from_currency'):
            log_entry["from_currency"] = record.from_currency
        if hasattr(record, 'to_currency'):
            log_entry["to_currency"] = record.to_currency
        
        # Добавляем контекст если есть
        if hasattr(record, 'context'):
            log_entry["context"] = record.context
        
        return json.dumps(log_entry, ensure_ascii=False)


class HumanReadableFormatter(logging.Formatter):
    """Форматтер для человеко-читаемых логов."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Форматирование записи лога в читаемом виде."""
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        
        # Базовое сообщение
        message_parts = [
            f"{record.levelname} {timestamp}",
            record.getMessage()
        ]
        
        # Добавляем дополнительные поля
        extra_fields = []
        if hasattr(record, 'action'):
            extra_fields.append(f"action={record.action}")
        if hasattr(record, 'username'):
            extra_fields.append(f"user='{record.username}'")
        if hasattr(record, 'user_id'):
            extra_fields.append(f"user_id={record.user_id}")
        if hasattr(record, 'currency_code'):
            extra_fields.append(f"currency='{record.currency_code}'")
        if hasattr(record, 'amount'):
            # Безопасное форматирование amount
            try:
                amount_value = float(record.amount)
                extra_fields.append(f"amount={amount_value:.4f}")
            except (ValueError, TypeError):
                extra_fields.append(f"amount={record.amount}")
        if hasattr(record, 'rate'):
            try:
                rate_value = float(record.rate)
                extra_fields.append(f"rate={rate_value:.2f}")
            except (ValueError, TypeError):
                extra_fields.append(f"rate={record.rate}")
        if hasattr(record, 'base_currency'):
            extra_fields.append(f"base='{record.base_currency}'")
        if hasattr(record, 'result'):
            extra_fields.append(f"result={record.result}")
        if hasattr(record, 'error_type'):
            extra_fields.append(f"error_type='{record.error_type}'")
        if hasattr(record, 'error_message'):
            # Обрезаем длинные сообщения об ошибках
            error_msg = record.error_message
            if len(error_msg) > 100:
                error_msg = error_msg[:97] + "..."
            extra_fields.append(f"error='{error_msg}'")
        
        if extra_fields:
            message_parts.append("[" + " ".join(extra_fields) + "]")
        
        return " ".join(message_parts)


def setup_logging() -> None:
    """Настройка системы логирования."""
    log_config = settings.get_log_config()
    
    # Создаем директорию для логов если не существует
    log_dir = os.path.dirname(log_config["file"])
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # Настройка корневого логгера
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_config["level"]))
    
    # Очищаем существующие обработчики
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Файловый обработчик с ротацией
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_config["file"],
        maxBytes=log_config["max_size_mb"] * 1024 * 1024,  # Конвертируем в байты
        backupCount=log_config["backup_count"],
        encoding='utf-8'
    )
    
    # Выбираем форматтер в зависимости от настройки
    use_json_format = settings.get("log_format_json", False)
    if use_json_format:
        formatter = JSONFormatter()
    else:
        formatter = HumanReadableFormatter()
    
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Консольный обработчик для разработки
    if settings.get("log_to_console", True):
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(HumanReadableFormatter())
        root_logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """Получить именованный логгер.
    
    Args:
        name: Имя логгера (обычно __name__ модуля)
        
    Returns:
        Настроенный логгер
    """
    return logging.getLogger(name)
