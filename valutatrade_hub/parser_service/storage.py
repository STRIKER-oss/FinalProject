"""Хранилище для курсов валют."""
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from ..infra.database import DatabaseManager


class RatesStorage:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.database = DatabaseManager()
        self.rates_file = os.path.join(data_dir, "rates.json")
        self.history_file = os.path.join(data_dir, "exchange_rates.json")
        
        os.makedirs(data_dir, exist_ok=True)
    
    def load_current_rates(self) -> Dict[str, Any]:
        try:
            return self.database.load_data(self.rates_file, default={})
        except Exception as e:
            print(f"Error loading current rates: {e}")
            return {}
    
    def save_current_rates(self, rates_data: Dict[str, Any]) -> None:
        try:
            self.database.save_data(rates_data, self.rates_file)
        except Exception as e:
            print(f"Error saving current rates: {e}")
            raise
    
    def load_historical_rates(self) -> Dict[str, Any]:
        try:
            return self.database.load_data(self.history_file, default={
                "version": "1.0",
                "last_updated": None,
                "rates_history": []
            })
        except Exception as e:
            print(f"Error loading historical rates: {e}")
            return {
                "version": "1.0",
                "last_updated": None,
                "rates_history": []
            }
    
    def save_historical_rates(self, historical_records: List[Dict[str, Any]]) -> None:
        try:
            history_data = self.load_historical_rates()
            
            if "rates_history" not in history_data:
                history_data["rates_history"] = []
            
            history_data["rates_history"].extend(historical_records)
            history_data["last_updated"] = datetime.now().isoformat()
            
            self.database.save_data(history_data, self.history_file)
            
        except Exception as e:
            print(f"Error saving historical rates: {e}")
            raise
    
    def get_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        rates_data = self.load_current_rates()
        pairs = rates_data.get('pairs', {})
        
        pair_key = f"{from_currency}_{to_currency}"
        if pair_key in pairs:
            rate_info = pairs[pair_key]
            if isinstance(rate_info, dict) and 'rate' in rate_info:
                return rate_info['rate']
        
        reverse_pair_key = f"{to_currency}_{from_currency}"
        if reverse_pair_key in pairs:
            rate_info = pairs[reverse_pair_key]
            if isinstance(rate_info, dict) and 'rate' in rate_info:
                return 1.0 / rate_info['rate']
        
        return None
    
    def get_all_rates(self) -> Dict[str, float]:
        rates_data = self.load_current_rates()
        pairs = rates_data.get('pairs', {})
        
        result = {}
        for pair_key, rate_info in pairs.items():
            if isinstance(rate_info, dict) and 'rate' in rate_info:
                result[pair_key] = rate_info['rate']
        
        return result
    
    def clear_cache(self) -> None:
        try:
            if os.path.exists(self.rates_file):
                os.remove(self.rates_file)
            self.database.clear_cache(self.rates_file)
        except Exception as e:
            print(f"Error clearing cache: {e}")
    
    def get_cache_info(self) -> Dict[str, Any]:
        rates_data = self.load_current_rates()
        history_data = self.load_historical_rates()
        
        return {
            "current_rates_count": len(rates_data.get('pairs', {})),
            "last_refresh": rates_data.get('last_refresh'),
            "historical_records_count": len(history_data.get('rates_history', [])),
            "history_last_updated": history_data.get('last_updated')
        }
