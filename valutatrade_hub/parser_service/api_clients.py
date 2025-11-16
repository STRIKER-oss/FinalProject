"""API клиенты для получения курсов валют."""
import requests
from abc import ABC, abstractmethod
from typing import Dict, Any
import time
from ..core.exceptions import ApiRequestError
from .config import config


class BaseApiClient(ABC):
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ValutatradeHub/1.0',
            'Accept': 'application/json'
        })
    
    @abstractmethod
    def fetch_rates(self) -> Dict[str, float]:
        pass
    
    def _make_request(self, url: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        start_time = time.time()
        
        try:
            response = self.session.get(
                url, 
                params=params, 
                timeout=config.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            
            request_time = int((time.time() - start_time) * 1000)
            
            return {
                'data': response.json(),
                'meta': {
                    'request_ms': request_time,
                    'status_code': response.status_code,
                    'etag': response.headers.get('ETag', '')
                }
            }
            
        except requests.exceptions.Timeout:
            raise ApiRequestError(f"Таймаут запроса к {self.__class__.__name__}")
            
        except requests.exceptions.ConnectionError:
            raise ApiRequestError(f"Ошибка подключения к {self.__class__.__name__}")
            
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else 'unknown'
            if status_code == 429:
                raise ApiRequestError(f"Превышен лимит запросов к {self.__class__.__name__}")
            elif status_code == 401:
                raise ApiRequestError(f"Неверный API ключ для {self.__class__.__name__}")
            else:
                raise ApiRequestError(f"HTTP ошибка {status_code} от {self.__class__.__name__}: {e}")
                
        except requests.exceptions.RequestException as e:
            raise ApiRequestError(f"Ошибка запроса к {self.__class__.__name__}: {e}")
            
        except ValueError as e:
            raise ApiRequestError(f"Ошибка парсинга JSON от {self.__class__.__name__}: {e}")


class CoinGeckoClient(BaseApiClient):
    def fetch_rates(self) -> Dict[str, float]:
        url = config.get_coingecko_url()
        
        try:
            result = self._make_request(url)
            
            rates = {}
            data = result['data']
            meta = result['meta']
            
            for crypto_code, gecko_id in config.CRYPTO_ID_MAP.items():
                if gecko_id in data and 'usd' in data[gecko_id]:
                    pair_key = f"{crypto_code}_{config.BASE_CURRENCY}"
                    rates[pair_key] = float(data[gecko_id]['usd'])
            
            if not rates:
                raise ApiRequestError("Не удалось получить курсы криптовалют от CoinGecko")
            
            rates['_meta'] = {
                'source': 'CoinGecko',
                'request_meta': meta
            }
            
            return rates
            
        except Exception as e:
            raise ApiRequestError(f"Ошибка при получении данных от CoinGecko: {e}")


class ExchangeRateApiClient(BaseApiClient):
    def fetch_rates(self) -> Dict[str, float]:
        url = config.get_exchangerate_api_url()
        
        try:
            result = self._make_request(url)
            
            rates = {}
            data = result['data']
            meta = result['meta']
            
            if data.get('result') != 'success':
                error_type = data.get('error-type', 'unknown')
                raise ApiRequestError(f"ExchangeRate-API вернул ошибку: {error_type}")
            
            base_currency = data.get('base_code', 'USD')
            rates_data = data.get('conversion_rates', {})
            
            for currency in config.FIAT_CURRENCIES:
                if currency in rates_data:
                    pair_key = f"{currency}_{config.BASE_CURRENCY}"
                    rates[pair_key] = float(rates_data[currency])
            
            if not rates:
                raise ApiRequestError("Не удалось получить курсы фиатных валют от ExchangeRate-API")
            
            rates['_meta'] = {
                'source': 'ExchangeRate-API', 
                'request_meta': meta,
                'base_currency': base_currency,
                'time_last_update_utc': data.get('time_last_update_utc')
            }
            
            return rates
            
        except Exception as e:
            raise ApiRequestError(f"Ошибка при получении данных от ExchangeRate-API: {e}")


class ApiClientFactory:
    @staticmethod
    def create_client(client_type: str) -> BaseApiClient:
        if client_type == 'coingecko':
            return CoinGeckoClient()
        elif client_type == 'exchangerate':
            return ExchangeRateApiClient()
        else:
            raise ValueError(f"Неизвестный тип клиента: {client_type}")
