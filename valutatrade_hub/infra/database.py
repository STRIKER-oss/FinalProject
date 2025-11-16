"""Singleton для управления JSON-хранилищем данных."""
import json
import os
from typing import Any, Dict, List, Optional
from ..core.exceptions import DatabaseError


class DatabaseManager:
    _instance: Optional['DatabaseManager'] = None
    _initialized: bool = False
    
    def __new__(cls) -> 'DatabaseManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        if not self._initialized:
            self._cache: Dict[str, Any] = {}
            self._initialized = True
    
    def load_data(self, file_path: str, default: Any = None) -> Any:
        try:
            if file_path in self._cache:
                return self._cache[file_path]
            
            if not os.path.exists(file_path):
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                self._cache[file_path] = default
                return default
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    self._cache[file_path] = default
                    return default
                
                data = json.loads(content)
                self._cache[file_path] = data
                return data
                
        except json.JSONDecodeError as e:
            raise DatabaseError(f"Ошибка формата JSON в файле {file_path}: {e}")
        except PermissionError as e:
            raise DatabaseError(f"Нет прав доступа к файлу {file_path}: {e}")
        except Exception as e:
            raise DatabaseError(f"Ошибка загрузки данных из {file_path}: {e}")
    
    def save_data(self, data: Any, file_path: str) -> None:
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            temp_file = file_path + '.tmp'
            
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            if os.path.exists(file_path):
                os.replace(temp_file, file_path)
            else:
                os.rename(temp_file, file_path)
            
            self._cache[file_path] = data
            
        except PermissionError as e:
            raise DatabaseError(f"Нет прав доступа для записи в файл {file_path}: {e}")
        except Exception as e:
            if os.path.exists(temp_file):
                os.remove(temp_file)
            raise DatabaseError(f"Ошибка сохранения данных в {file_path}: {e}")
    
    def clear_cache(self, file_path: Optional[str] = None) -> None:
        if file_path:
            self._cache.pop(file_path, None)
        else:
            self._cache.clear()
    
    def get_cached_files(self) -> List[str]:
        return list(self._cache.keys())
    
    def backup_data(self, file_path: str, backup_suffix: str = '.bak') -> None:
        try:
            if not os.path.exists(file_path):
                return
            
            backup_path = file_path + backup_suffix
            import shutil
            shutil.copy2(file_path, backup_path)
            
        except Exception as e:
            raise DatabaseError(f"Ошибка создания резервной копии {file_path}: {e}")
    
    def exists(self, file_path: str) -> bool:
        return os.path.exists(file_path)
