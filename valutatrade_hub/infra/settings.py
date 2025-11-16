"""Singleton для загрузки и управления конфигурацией приложения."""
import os
import json
from typing import Any, Dict, Optional


class SettingsLoader:
    _instance: Optional['SettingsLoader'] = None
    _initialized: bool = False
    
    def __new__(cls) -> 'SettingsLoader':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        if not self._initialized:
            self._config: Dict[str, Any] = {}
            self._load_config()
            self._initialized = True
    
    def _load_config(self) -> None:
        default_config = {
            "data_dir": "data",
            "rates_ttl_seconds": 300,
            "default_base_currency": "USD",
            "log_level": "INFO",
            "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "log_file": "logs/valutatrade.log",
            "max_log_size_mb": 10,
            "backup_count": 5,
            "supported_currencies": ["USD", "EUR", "GBP", "JPY", "RUB", "CNY", "BTC", "ETH", "LTC", "XRP", "ADA"]
        }
        
        config_path = "config.json"
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    file_config = json.load(f)
                
                for key, value in file_config.items():
                    if key in default_config:
                        default_config[key] = value
                
            except Exception as e:
                print(f"Warning: Could not load config.json: {e}. Using default settings.")
        
        env_mappings = {
            "VALUTATRADE_DATA_DIR": "data_dir",
            "VALUTATRADE_RATES_TTL": "rates_ttl_seconds",
            "VALUTATRADE_BASE_CURRENCY": "default_base_currency",
            "VALUTATRADE_LOG_LEVEL": "log_level",
            "VALUTATRADE_LOG_FILE": "log_file"
        }
        
        for env_var, config_key in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                if config_key == "rates_ttl_seconds":
                    try:
                        default_config[config_key] = int(env_value)
                    except ValueError:
                        pass
                else:
                    default_config[config_key] = env_value
        
        self._config = default_config
    
    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)
    
    def reload(self) -> None:
        self._config.clear()
        self._load_config()
    
    def get_data_dir(self) -> str:
        return self.get("data_dir", "data")
    
    def get_rates_ttl(self) -> int:
        return self.get("rates_ttl_seconds", 300)
    
    def get_default_base_currency(self) -> str:
        return self.get("default_base_currency", "USD")
    
    def get_log_config(self) -> Dict[str, Any]:
        return {
            "level": self.get("log_level", "INFO"),
            "format": self.get("log_format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
            "file": self.get("log_file", "logs/valutatrade.log"),
            "max_size_mb": self.get("max_log_size_mb", 10),
            "backup_count": self.get("backup_count", 5)
        }
    
    def get_supported_currencies(self) -> list:
        return self.get("supported_currencies", [])
    
    def __getitem__(self, key: str) -> Any:
        return self._config[key]
    
    def __contains__(self, key: str) -> bool:
        return key in self._config


settings = SettingsLoader()
