"""Планировщик периодического обновления курсов валют."""
import threading
import logging
from datetime import datetime, timedelta
from typing import Optional, Callable
from .updater import RatesUpdater
from .config import config


logger = logging.getLogger(__name__)


class RatesScheduler:
    def __init__(self, updater: Optional[RatesUpdater] = None):
        self.updater = updater or RatesUpdater()
        self._scheduler_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._is_running = False
        self._last_run: Optional[datetime] = None
        self._next_run: Optional[datetime] = None
        self._update_callback: Optional[Callable] = None
        
        self.successful_runs = 0
        self.failed_runs = 0
        self.total_runs = 0
    
    def start(self, daemon: bool = True) -> None:
        if self._is_running:
            logger.warning("Планировщик уже запущен")
            return
        
        self._stop_event.clear()
        self._is_running = True
        
        self._scheduler_thread = threading.Thread(
            target=self._run_scheduler,
            daemon=daemon,
            name="RatesScheduler"
        )
        self._scheduler_thread.start()
        
        logger.info(f"Планировщик запущен. Интервал обновления: {config.UPDATE_INTERVAL_MINUTES} минут")
    
    def stop(self) -> None:
        if not self._is_running:
            return
        
        self._stop_event.set()
        self._is_running = False
        
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=5.0)
        
        logger.info("Планировщик остановлен")
    
    def _run_scheduler(self) -> None:
        logger.info("Запуск основного цикла планировщика")
        
        self._run_update()
        
        while not self._stop_event.is_set():
            try:
                next_run_time = datetime.now() + timedelta(minutes=config.UPDATE_INTERVAL_MINUTES)
                self._next_run = next_run_time
                
                wait_seconds = (next_run_time - datetime.now()).total_seconds()
                
                if wait_seconds > 0:
                    logger.debug(f"Следующее обновление через {wait_seconds:.0f} секунд")
                    self._stop_event.wait(min(wait_seconds, 60))
                
                if not self._stop_event.is_set():
                    self._run_update()
                    
            except Exception as e:
                logger.error(f"Ошибка в цикле планировщика: {e}")
                self._stop_event.wait(60)
    
    def _run_update(self) -> None:
        try:
            logger.info("Запуск запланированного обновления курсов")
            self.total_runs += 1
            
            result = self.updater.run_update()
            self._last_run = datetime.now()
            
            if result.get('failed'):
                self.failed_runs += 1
                logger.warning(f"Обновление завершено с ошибками. Успешно: {len(result['successful'])}, Ошибок: {len(result['failed'])}")
            else:
                self.successful_runs += 1
                logger.info(f"Обновление завершено успешно. Курсов обновлено: {result['total_rates']}")
            
            if self._update_callback:
                try:
                    self._update_callback(result)
                except Exception as e:
                    logger.error(f"Ошибка в callback: {e}")
                    
        except Exception as e:
            self.failed_runs += 1
            logger.error(f"Ошибка при выполнении обновления: {e}")
    
    def run_once(self) -> dict:
        logger.info("Запуск однократного обновления по требованию")
        return self._run_update()
    
    def set_update_callback(self, callback: Callable) -> None:
        self._update_callback = callback
        logger.debug("Callback установлен")
    
    def get_status(self) -> dict:
        status = {
            "is_running": self._is_running,
            "total_runs": self.total_runs,
            "successful_runs": self.successful_runs,
            "failed_runs": self.failed_runs,
            "success_rate": (
                self.successful_runs / self.total_runs 
                if self.total_runs > 0 else 0
            ),
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "next_run": self._next_run.isoformat() if self._next_run else None,
            "update_interval_minutes": config.UPDATE_INTERVAL_MINUTES
        }
        
        if hasattr(self.updater, 'get_status'):
            status["updater"] = self.updater.get_status()
        
        return status
    
    def force_update(self) -> dict:
        logger.info("Принудительное обновление запущено")
        return self._run_update()
    
    def change_interval(self, minutes: int) -> None:
        if minutes <= 0:
            raise ValueError("Интервал должен быть положительным числом")
        
        config.UPDATE_INTERVAL_MINUTES = minutes
        logger.info(f"Интервал обновления изменен на {minutes} минут")
        
        if self._is_running:
            self.stop()
            self.start()


_scheduler_instance: Optional[RatesScheduler] = None


def get_scheduler() -> RatesScheduler:
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = RatesScheduler()
    return _scheduler_instance


def start_scheduler(daemon: bool = True) -> None:
    scheduler = get_scheduler()
    scheduler.start(daemon=daemon)


def stop_scheduler() -> None:
    global _scheduler_instance
    if _scheduler_instance:
        _scheduler_instance.stop()
        _scheduler_instance = None


def scheduler_status() -> dict:
    scheduler = get_scheduler()
    return scheduler.get_status()
