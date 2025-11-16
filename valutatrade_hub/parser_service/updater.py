"""Модуль обновления курсов валют."""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List
from .api_clients import BaseApiClient, ApiClientFactory
from .storage import RatesStorage


logger = logging.getLogger(__name__)


class RatesUpdater:
    def __init__(self, storage: RatesStorage = None, clients: List[BaseApiClient] = None):
        self.storage = storage or RatesStorage()
        
        if clients:
            self.clients = clients
        else:
            self.clients = [
                ApiClientFactory.create_client('exchangerate'),
                ApiClientFactory.create_client('coingecko')
            ]
        
        self.successful_updates = 0
        self.failed_updates = 0
    
    def run_update(self) -> Dict[str, Any]:
        logger.info("Запуск обновления курсов валют")
        
        current_time = datetime.now(timezone.utc).isoformat()
        all_rates = {}
        update_results = {
            'successful': [],
            'failed': [],
            'total_rates': 0,
            'timestamp': current_time
        }
        
        for client in self.clients:
            client_name = client.__class__.__name__
            
            try:
                logger.info(f"Опрос клиента: {client_name}")
                rates_data = client.fetch_rates()
                
                meta_info = rates_data.pop('_meta', {})
                source = meta_info.get('source', client_name)
                
                for pair, rate in rates_data.items():
                    all_rates[pair] = {
                        'rate': rate,
                        'updated_at': current_time,
                        'source': source
                    }
                
                self._save_historical_data(rates_data, source, meta_info, current_time)
                
                self.successful_updates += 1
                update_results['successful'].append({
                    'client': client_name,
                    'rates_count': len(rates_data),
                    'source': source
                })
                
                logger.info(f"Клиент {client_name} успешно обновил {len(rates_data)} курсов")
                
            except Exception as e:
                self.failed_updates += 1
                error_info = {
                    'client': client_name,
                    'error': str(e),
                    'error_type': e.__class__.__name__
                }
                update_results['failed'].append(error_info)
                logger.error(f"Ошибка в клиенте {client_name}: {e}")
        
        if not all_rates:
            error_msg = "Все клиенты завершились с ошибкой. Курсы не обновлены."
            logger.error(error_msg)
            raise Exception(error_msg)
        
        final_result = {
            'pairs': all_rates,
            'last_refresh': current_time
        }
        
        self.storage.save_current_rates(final_result)
        
        update_results['total_rates'] = len(all_rates)
        
        logger.info(
            f"Обновление завершено. Успешно: {self.successful_updates}, "
            f"Ошибок: {self.failed_updates}, Всего курсов: {len(all_rates)}"
        )
        
        return update_results
    
    def _save_historical_data(self, rates_data: Dict[str, float], source: str, 
                            meta_info: Dict[str, Any], timestamp: str) -> None:
        historical_records = []
        
        for pair, rate in rates_data.items():
            if '_' in pair:
                from_currency, to_currency = pair.split('_', 1)
            else:
                logger.warning(f"Некорректный формат пары: {pair}")
                continue
            
            record_id = f"{pair}_{timestamp.replace(':', '-').replace('.', '-')}"
            
            record = {
                'id': record_id,
                'from_currency': from_currency,
                'to_currency': to_currency,
                'rate': rate,
                'timestamp': timestamp,
                'source': source,
                'meta': {
                    'raw_id': meta_info.get('raw_id', ''),
                    'request_ms': meta_info.get('request_meta', {}).get('request_ms', 0),
                    'status_code': meta_info.get('request_meta', {}).get('status_code', 0),
                    'etag': meta_info.get('request_meta', {}).get('etag', '')
                }
            }
            
            if source == 'ExchangeRate-API':
                record['meta']['base_currency'] = meta_info.get('base_currency', 'USD')
                record['meta']['time_last_update_utc'] = meta_info.get('time_last_update_utc', '')
            
            historical_records.append(record)
        
        if historical_records:
            self.storage.save_historical_rates(historical_records)
    
    def get_status(self) -> Dict[str, Any]:
        return {
            'total_clients': len(self.clients),
            'successful_updates': self.successful_updates,
            'failed_updates': self.failed_updates,
            'success_rate': (
                self.successful_updates / (self.successful_updates + self.failed_updates) 
                if (self.successful_updates + self.failed_updates) > 0 else 0
            )
        }
