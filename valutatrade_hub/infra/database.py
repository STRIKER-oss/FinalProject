"""Singleton для управления JSON-хранилищем данных."""
import json
import os
from typing import Any, Dict, List, Optional
from ..core.exceptions import DatabaseError


class DatabaseManager:
    """Singleton для абстракции над JSON-хранилищем."""
    
    _instance: Optional['DatabaseManager'] = None
    _initialized: bool = False
    
    def __new__(cls) -> 'DatabaseManager':
        """Реализация Singleton через __new__.
        
        Выбран этот способ потому что:
        - Проще и читабельнее метаклассов
        - Легче понять и поддерживать
        - Достаточно для задачи гарантии единственного экземпляра
        - Стандартный подход в Python
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        """Инициализация менеджера базы данных (выполняется только один раз)."""
        if not self._initialized:
            self._cache: Dict[str, Any] = {}
            self._initialized = True
    
    def load_data(self, file_path: str, default: Any = None) -> Any:
        """Безопасная загрузка данных из JSON файла.
        
        Args:
            file_path: Путь к JSON файлу
            default: Значение по умолчанию, если файл не существует или поврежден
            
        Returns:
            Загруженные данные или default
            
        Raises:
            DatabaseError: При критических ошибках чтения
        """
        try:
            # Проверяем кеш для оптимизации частых чтений
            if file_path in self._cache:
                return self._cache[file_path]
            
            if not os.path.exists(file_path):
                # Создаем директорию если не существует
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
        """Безопасное сохранение данных в JSON файл.
        
        Args:
            data: Данные для сохранения
            file_path: Путь к JSON файлу
            
        Raises:
            DatabaseError: При ошибках записи
        """
        try:
            # Создаем директорию если не существует
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Создаем временный файл для атомарной записи
            temp_file = file_path + '.tmp'
            
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Атомарно заменяем старый файл новым
            if os.path.exists(file_path):
                os.replace(temp_file, file_path)
            else:
                os.rename(temp_file, file_path)
            
            # Обновляем кеш
            self._cache[file_path] = data
            
        except PermissionError as e:
            raise DatabaseError(f"Нет прав доступа для записи в файл {file_path}: {e}")
        except Exception as e:
            # Удаляем временный файл в случае ошибки
            if os.path.exists(temp_file):
                os.remove(temp_file)
            raise DatabaseError(f"Ошибка сохранения данных в {file_path}: {e}")
    
    def clear_cache(self, file_path: Optional[str] = None) -> None:
        """Очистка кеша.
        
        Args:
            file_path: Очистить кеш для конкретного файла, если None - очистить весь кеш
        """
        if file_path:
            self._cache.pop(file_path, None)
        else:
            self._cache.clear()
    
    def get_cached_files(self) -> List[str]:
        """Получить список файлов в кеше.
        
        Returns:
            Список путей к файлам в кеше
        """
        return list(self._cache.keys())
    
    def backup_data(self, file_path: str, backup_suffix: str = '.bak') -> None:
        """Создание резервной копии данных.
        
        Args:
            file_path: Путь к файлу для резервного копирования
            backup_suffix: Суффикс для файла бэкапа
            
        Raises:
            DatabaseError: При ошибках создания бэкапа
        """
        try:
            if not os.path.exists(file_path):
                return
            
            backup_path = file_path + backup_suffix
            import shutil
            shutil.copy2(file_path, backup_path)
            
        except Exception as e:
            raise DatabaseError(f"Ошибка создания резервной копии {file_path}: {e}")
    
    def exists(self, file_path: str) -> bool:
        """Проверка существования файла.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            True если файл существует, иначе False
        """
        return os.path.exists(file_path)
