"""Командный интерфейс приложения."""
import argparse
from prettytable import PrettyTable
from ..core.usecases import UserManager, PortfolioManager, CurrencyManager
from ..core.exceptions import (
    InsufficientFundsError, CurrencyNotFoundError, ApiRequestError,
    UserNotFoundError, UserAlreadyExistsError, InvalidPasswordError,
    WalletNotFoundError, InvalidAmountError, ExchangeRateUnavailableError
)
from ..core.utils import format_datetime
from ..core.currencies import CurrencyRegistry
from ..infra.settings import settings
from ..logging_config import get_logger
from ..parser_service.updater import RatesUpdater
from ..parser_service.storage import RatesStorage
from ..parser_service.api_clients import ApiClientFactory


class CLIInterface:
    def __init__(self):
        self.user_manager = UserManager()
        self.currency_manager = CurrencyManager()
        self.portfolio_manager = PortfolioManager(user_manager=self.user_manager)
        self.current_user = None
        self.rates_storage = RatesStorage()
    
    def print_help(self):
        print("\n=== Биржевой помощник - Доступные команды ===")
        print("register --username <name> --password <pass>  - Регистрация")
        print("login --username <name> --password <pass>     - Вход в систему")
        print("show-portfolio [--base <curr>]                - Показать портфель")
        print("buy --currency <curr> --amount <num>          - Купить валюту")
        print("sell --currency <curr> --amount <num>         - Продать валюту")
        print("get-rate --from <curr> --to <curr>            - Получить курс")
        print("update-rates [--source <src>]                 - Обновить курсы валют")
        print("show-rates [--currency <curr>] [--top <n>] [--base <curr>] - Показать курсы")
        print("list-currencies                               - Список валют")
        print("help                                          - Показать справку")
        print("exit                                          - Выйти")
        print("\nПримеры:")
        print("  buy --currency EUR --amount 100")
        print("  sell --currency BTC --amount 0.5")
        print("  get-rate --from USD --to EUR")
        print("  show-portfolio --base EUR")
        print("  update-rates --source coingecko")
        print("  show-rates --top 5 --base EUR")
    
    def run(self):
        print("Добро пожаловать в Биржевой помощник!")
        print("Введите 'help' для списка команд или 'exit' для выхода.")
        
        while True:
            try:
                if self.current_user:
                    prompt = f"\n[{self.current_user.username}]> "
                else:
                    prompt = "\n[guest]> "
                
                user_input = input(prompt).strip()
                
                if user_input == "exit":
                    print("До свидания!")
                    break
                elif user_input == "help":
                    self.print_help()
                elif user_input == "list-currencies":
                    self.list_currencies()
                elif user_input.startswith("show-portfolio"):
                    self.handle_show_portfolio(user_input.split()[1:])
                elif user_input.startswith("update-rates"):
                    self.handle_update_rates(user_input.split()[1:])
                elif user_input.startswith("show-rates"):
                    self.handle_show_rates(user_input.split()[1:])
                elif user_input == "":
                    continue
                else:
                    self.parse_command(user_input)
            
            except KeyboardInterrupt:
                print("\n\nДо свидания!")
                break
            except Exception as e:
                print(f"Ошибка: {e}")
    
    def parse_command(self, command_line: str):
        parts = command_line.split()
        if not parts:
            return
        
        command = parts[0]
        args = parts[1:]
        
        if command == "register":
            self.handle_register(args)
        elif command == "login":
            self.handle_login(args)
        elif command == "buy":
            self.handle_buy(args)
        elif command == "sell":
            self.handle_sell(args)
        elif command == "get-rate":
            self.handle_get_rate(args)
        else:
            print("Неизвестная команда. Введите 'help' для списка команд.")
    
    def handle_update_rates(self, args):
        parser = argparse.ArgumentParser(prog='update-rates', add_help=False)
        parser.add_argument('--source', choices=['coingecko', 'exchangerate'], 
                          help='Источник данных')
        
        try:
            parsed_args = parser.parse_args(args)
            self.update_rates(parsed_args.source)
        except SystemExit:
            print("Использование: update-rates [--source <coingecko|exchangerate>]")
        except Exception as e:
            print(f"Ошибка: {e}")
    
    def update_rates(self, source: str = None):
        print("Запуск обновления курсов валют...")
        
        try:
            clients = []
            if source is None:
                clients.append(ApiClientFactory.create_client('exchangerate'))
                clients.append(ApiClientFactory.create_client('coingecko'))
            elif source == 'coingecko':
                clients.append(ApiClientFactory.create_client('coingecko'))
            elif source == 'exchangerate':
                clients.append(ApiClientFactory.create_client('exchangerate'))
            
            updater = RatesUpdater(clients=clients)
            result = updater.run_update()
            
            print("Обновление завершено успешно!")
            print(f"Всего обновлено курсов: {result['total_rates']}")
            print(f"Время обновления: {result['timestamp']}")
            
            if result['successful']:
                print("\nУспешные обновления:")
                for success in result['successful']:
                    print(f"  - {success['client']}: {success['rates_count']} курсов")
            
            if result['failed']:
                print("\nОшибки:")
                for error in result['failed']:
                    print(f"  - {error['client']}: {error['error']}")
                
        except ApiRequestError as e:
            print(f"Ошибка при обновлении курсов: {e}")
            print("Проверьте подключение к интернету и повторите попытку")
        except Exception as e:
            print(f"Не удалось обновить курсы: {e}")
    
    def handle_show_rates(self, args):
        parser = argparse.ArgumentParser(prog='show-rates', add_help=False)
        parser.add_argument('--currency', help='Показать курс только для указанной валюты')
        parser.add_argument('--top', type=int, help='Показать N самых дорогих криптовалют')
        parser.add_argument('--base', default='USD', help='Базовая валюта для отображения')
        
        try:
            parsed_args = parser.parse_args(args)
            self.show_rates(parsed_args.currency, parsed_args.top, parsed_args.base)
        except SystemExit:
            print("Использование: show-rates [--currency <curr>] [--top <n>] [--base <curr>]")
        except Exception as e:
            print(f"Ошибка: {e}")
    
    def show_rates(self, currency: str = None, top: int = None, base_currency: str = 'USD'):
        try:
            rates_data = self.rates_storage.load_current_rates()
            
            if not rates_data or 'pairs' not in rates_data or not rates_data['pairs']:
                print("Локальный кеш курсов пуст. Выполните 'update-rates', чтобы загрузить данные.")
                return
            
            pairs = rates_data['pairs']
            last_refresh = rates_data.get('last_refresh', 'Неизвестно')
            
            filtered_rates = {}
            
            for pair_key, rate_info in pairs.items():
                if '_' not in pair_key:
                    continue
                
                from_curr, to_curr = pair_key.split('_', 1)
                
                if currency and from_curr != currency.upper() and to_curr != currency.upper():
                    continue
                
                if base_currency.upper() != 'USD':
                    if to_curr == 'USD':
                        try:
                            base_rate = self.currency_manager.get_rate('USD', base_currency.upper())
                            converted_rate = rate_info['rate'] * base_rate
                            display_pair = f"{from_curr}_{base_currency.upper()}"
                            filtered_rates[display_pair] = {
                                'rate': converted_rate,
                                'updated_at': rate_info.get('updated_at', ''),
                                'source': rate_info.get('source', '')
                            }
                        except (CurrencyNotFoundError, ExchangeRateUnavailableError):
                            continue
                    else:
                        continue
                else:
                    filtered_rates[pair_key] = rate_info
            
            if not filtered_rates:
                if currency:
                    print(f"Курс для '{currency}' не найден в кеше.")
                else:
                    print("Нет данных для отображения с указанными фильтрами.")
                return
            
            sorted_rates = sorted(
                filtered_rates.items(),
                key=lambda x: x[1]['rate'] if top else x[0]
            )
            
            if top and top > 0:
                sorted_rates = sorted(
                    filtered_rates.items(),
                    key=lambda x: x[1]['rate'],
                    reverse=True
                )[:top]
            
            print(f"\nКурсы из кеша (обновлено: {format_datetime(last_refresh)}):")
            print("-" * 80)
            
            table = PrettyTable()
            table.field_names = ["Валютная пара", "Курс", "Обновлено", "Источник"]
            table.align = "r"
            table.align["Валютная пара"] = "l"
            table.align["Источник"] = "l"
            
            for pair_key, rate_info in sorted_rates:
                rate = rate_info['rate']
                updated_at = format_datetime(rate_info.get('updated_at', ''))
                source = rate_info.get('source', 'Неизвестно')
                
                if rate >= 1000:
                    rate_str = f"{rate:,.2f}"
                elif rate >= 1:
                    rate_str = f"{rate:.4f}"
                elif rate >= 0.01:
                    rate_str = f"{rate:.6f}"
                else:
                    rate_str = f"{rate:.8f}"
                
                table.add_row([pair_key, rate_str, updated_at, source])
            
            print(table)
            print(f"Всего курсов: {len(sorted_rates)}")
            
        except FileNotFoundError:
            print("Локальный кеш курсов пуст. Выполните 'update-rates', чтобы загрузить данные.")
        except Exception as e:
            print(f"Ошибка при загрузке курсов: {e}")
    
    def handle_show_portfolio(self, args):
        parser = argparse.ArgumentParser(prog='show-portfolio', add_help=False)
        parser.add_argument('--base', default=settings.get_default_base_currency(), 
                          help='Базовая валюта конвертации')
        
        try:
            parsed_args = parser.parse_args(args)
            self.show_portfolio(parsed_args.base)
        except SystemExit:
            print("Использование: show-portfolio [--base <curr>]")
        except Exception as e:
            print(f"Ошибка: {e}")
    
    def show_portfolio(self, base_currency: str = None):
        if not self.current_user:
            print("Ошибка: Сначала выполните вход в систему (login)")
            return
        
        if base_currency is None:
            base_currency = settings.get_default_base_currency()
        
        base_currency = base_currency.upper()
        
        try:
            CurrencyRegistry.get_currency(base_currency)
        except CurrencyNotFoundError:
            print(f"Ошибка: Неизвестная базовая валюта '{base_currency}'")
            print("Используйте 'list-currencies' для просмотра поддерживаемых валют")
            return
        
        try:
            portfolio = self.portfolio_manager.get_portfolio(self.current_user.user_id)
            wallets = portfolio.wallets
            
            if not wallets:
                print("Ваш портфель пуст. Используйте 'buy' для покупки валюты.")
                return
            
            print(f"\nПортфель пользователя '{self.current_user.username}' (базовая валюта: {base_currency}):")
            print("-" * 60)
            
            total_value = 0.0
            table = PrettyTable()
            table.field_names = ["Валюта", "Баланс", "Курс к базовой", "Стоимость в базовой"]
            table.align = "r"
            table.align["Валюта"] = "l"
            
            for currency_code, wallet in wallets.items():
                balance = wallet.balance
                
                if currency_code == base_currency:
                    value_in_base = balance
                    rate_info = "1.0000"
                else:
                    try:
                        exchange_rate = self.currency_manager.get_rate(currency_code, base_currency)
                        if exchange_rate:
                            value_in_base = balance * exchange_rate
                            rate_info = f"{exchange_rate:.4f}"
                        else:
                            value_in_base = 0.0
                            rate_info = "N/A"
                    except (CurrencyNotFoundError, ExchangeRateUnavailableError, ApiRequestError):
                        value_in_base = 0.0
                        rate_info = "N/A"
                
                total_value += value_in_base
                
                table.add_row([
                    f"{currency_code}",
                    f"{balance:.4f}",
                    f"{rate_info}",
                    f"{value_in_base:.2f} {base_currency}"
                ])
            
            print(table)
            print("-" * 60)
            print(f"ИТОГО: {total_value:,.2f} {base_currency}")
            
        except Exception as e:
            print(f"Ошибка при загрузке портфеля: {e}")
    
    def handle_register(self, args):
        parser = argparse.ArgumentParser(prog='register', add_help=False)
        parser.add_argument('--username', required=True, help='Имя пользователя')
        parser.add_argument('--password', required=True, help='Пароль')
        
        try:
            parsed_args = parser.parse_args(args)
            self.register(parsed_args.username, parsed_args.password)
        except SystemExit:
            print("Использование: register --username <name> --password <pass>")
        except UserAlreadyExistsError as e:
            print(f"{e}")
        except ValueError as e:
            print(f"Ошибка валидации: {e}")
        except Exception as e:
            print(f"Неожиданная ошибка: {e}")
    
    def register(self, username: str, password: str):
        try:
            if self.user_manager.register_user(username, password):
                user = self.user_manager.find_user_by_username(username)
                print(f"Пользователь '{username}' успешно зарегистрирован (id={user.user_id})")
                print("На ваш счет зачислено 10,000 USD стартового капитала")
                print(f"Теперь вы можете войти: login --username {username} --password [ваш пароль]")
        except UserAlreadyExistsError as e:
            print(f"{e}")
        except ValueError as e:
            print(f"Ошибка валидации: {e}")
        except Exception as e:
            print(f"Ошибка при регистрации: {e}")
    
    def handle_login(self, args):
        parser = argparse.ArgumentParser(prog='login', add_help=False)
        parser.add_argument('--username', required=True, help='Имя пользователя')
        parser.add_argument('--password', required=True, help='Пароль')
        
        try:
            parsed_args = parser.parse_args(args)
            self.login(parsed_args.username, parsed_args.password)
        except SystemExit:
            print("Использование: login --username <name> --password <pass>")
        except (UserNotFoundError, InvalidPasswordError) as e:
            print(f"{e}")
        except Exception as e:
            print(f"Неожиданная ошибка: {e}")
    
    def login(self, username: str, password: str):
        try:
            if self.user_manager.authenticate_user(username, password):
                self.current_user = self.user_manager.find_user_by_username(username)
                print(f"Вы успешно вошли как '{username}'")
                print("Для просмотра портфеля используйте: show-portfolio")
        except (UserNotFoundError, InvalidPasswordError) as e:
            print(f"{e}")
        except Exception as e:
            print(f"Ошибка при входе: {e}")
    
    def handle_buy(self, args):
        if not self.current_user:
            print("Ошибка: Для покупки валюты необходимо войти в систему")
            return
        
        parser = argparse.ArgumentParser(prog='buy', add_help=False)
        parser.add_argument('--currency', required=True, help='Код покупаемой валюты')
        parser.add_argument('--amount', required=True, type=float, help='Количество покупаемой валюты')
        
        try:
            parsed_args = parser.parse_args(args)
            self.buy_currency(parsed_args.currency, parsed_args.amount)
        except SystemExit:
            print("Использование: buy --currency <curr> --amount <num>")
        except (CurrencyNotFoundError, InvalidAmountError, InsufficientFundsError, 
                ExchangeRateUnavailableError, ApiRequestError, ValueError) as e:
            print(f"{e}")
        except Exception as e:
            print(f"Неожиданная ошибка: {e}")
    
    def buy_currency(self, currency: str, amount: float):
        currency = currency.upper()
        
        try:
            CurrencyRegistry.get_currency(currency)
            
            portfolio = self.portfolio_manager.get_portfolio(self.current_user.user_id)
            old_balance = portfolio.get_balance(currency)
            old_usd_balance = portfolio.get_balance("USD")
            
            exchange_rate = self.currency_manager.get_rate("USD", currency)
            purchase_cost = amount * exchange_rate
            
            print(f"Покупка {amount:.4f} {currency}...")
            print(f"Стоимость покупки: {purchase_cost:.2f} USD")
            print(f"Курс: 1 {currency} = {exchange_rate:.2f} USD")
            
            if self.portfolio_manager.buy_currency(self.current_user.user_id, currency, amount):
                new_balance = portfolio.get_balance(currency)
                new_usd_balance = portfolio.get_balance("USD")
                
                print("Покупка выполнена успешно!")
                print("\nИзменения в портфеле:")
                print(f"   {currency}: {old_balance:.4f} → {new_balance:.4f} (+{amount:.4f})")
                print(f"   USD: {old_usd_balance:.2f} → {new_usd_balance:.2f} (-{purchase_cost:.2f})")
                
        except CurrencyNotFoundError as e:
            print(f"{e}")
            print("Используйте 'list-currencies' для просмотра поддерживаемых валют")
        except InsufficientFundsError as e:
            print(f"{e}")
            print("Недостаточно USD для покупки")
        except ExchangeRateUnavailableError as e:
            print(f"{e}")
            print("Повторите попытку позже")
        except ApiRequestError as e:
            print(f"{e}")
            print("Проверьте подключение к интернету и повторите попытку")
        except InvalidAmountError as e:
            print(f"{e}")
            print("Сумма должна быть положительным числом")
        except ValueError as e:
            print(f"{e}")
        except Exception as e:
            print(f"Не удалось выполнить покупку: {e}")
    
    def handle_sell(self, args):
        if not self.current_user:
            print("Ошибка: Для продажи валюты необходимо войти в систему")
            return
        
        parser = argparse.ArgumentParser(prog='sell', add_help=False)
        parser.add_argument('--currency', required=True, help='Код продаваемой валюты')
        parser.add_argument('--amount', required=True, type=float, help='Количество продаваемой валюты')
        
        try:
            parsed_args = parser.parse_args(args)
            self.sell_currency(parsed_args.currency, parsed_args.amount)
        except SystemExit:
            print("Использование: sell --currency <curr> --amount <num>")
        except (CurrencyNotFoundError, InvalidAmountError, InsufficientFundsError, 
                WalletNotFoundError, ExchangeRateUnavailableError, ApiRequestError, ValueError) as e:
            print(f"{e}")
        except Exception as e:
            print(f"Неожиданная ошибка: {e}")
    
    def sell_currency(self, currency: str, amount: float):
        currency = currency.upper()
        
        try:
            CurrencyRegistry.get_currency(currency)
            
            portfolio = self.portfolio_manager.get_portfolio(self.current_user.user_id)
            old_balance = portfolio.get_balance(currency)
            old_usd_balance = portfolio.get_balance("USD")
            
            exchange_rate = self.currency_manager.get_rate(currency, "USD")
            usd_revenue = amount * exchange_rate
            
            print(f"Продажа {amount:.4f} {currency}...")
            print(f"Ожидаемая выручка: {usd_revenue:.2f} USD")
            print(f"Курс: 1 {currency} = {exchange_rate:.2f} USD")
            
            if old_balance < amount:
                raise InsufficientFundsError(
                    currency_code=currency,
                    available=old_balance,
                    required=amount
                )
            
            if self.portfolio_manager.sell_currency(self.current_user.user_id, currency, amount):
                new_balance = portfolio.get_balance(currency)
                new_usd_balance = portfolio.get_balance("USD")
                
                print("Продажа выполнена успешно!")
                print("\nИзменения в портфеле:")
                print(f"   {currency}: {old_balance:.4f} → {new_balance:.4f} (-{amount:.4f})")
                print(f"   USD: {old_usd_balance:.2f} → {new_usd_balance:.2f} (+{usd_revenue:.2f})")
                
        except CurrencyNotFoundError as e:
            print(f"{e}")
            print("Используйте 'list-currencies' для просмотра поддерживаемых валют")
        except InsufficientFundsError as e:
            print(f"{e}")
            print("У вас недостаточно валюты для продажи")
        except WalletNotFoundError as e:
            print(f"{e}")
            print("У вас нет кошелька с этой валютой")
        except ExchangeRateUnavailableError as e:
            print(f"{e}")
            print("Повторите попытку позже")
        except ApiRequestError as e:
            print(f"{e}")
            print("Проверьте подключение к интернету и повторите попытку")
        except InvalidAmountError as e:
            print(f"{e}")
            print("Сумма должна быть положительным числом")
        except ValueError as e:
            print(f"{e}")
        except Exception as e:
            print(f"Не удалось выполнить продажу: {e}")
    
    def handle_get_rate(self, args):
        parser = argparse.ArgumentParser(prog='get-rate', add_help=False)
        parser.add_argument('--from', required=True, dest='from_currency', help='Исходная валюта')
        parser.add_argument('--to', required=True, dest='to_currency', help='Целевая валюта')
        
        try:
            parsed_args = parser.parse_args(args)
            self.get_rate(parsed_args.from_currency, parsed_args.to_currency)
        except SystemExit:
            print("Использование: get-rate --from <curr> --to <curr>")
        except (CurrencyNotFoundError, ApiRequestError, ExchangeRateUnavailableError) as e:
            print(f"{e}")
            if isinstance(e, CurrencyNotFoundError):
                print("Используйте 'list-currencies' для просмотра поддерживаемых валют")
            elif isinstance(e, (ApiRequestError, ExchangeRateUnavailableError)):
                print("Повторите попытку позже или проверьте подключение к сети")
        except Exception as e:
            print(f"Неожиданная ошибка: {e}")
    
    def get_rate(self, from_currency: str, to_currency: str):
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()
        
        try:
            CurrencyRegistry.get_currency(from_currency)
            CurrencyRegistry.get_currency(to_currency)
            
            rate_info = self.currency_manager.get_rate_with_info(from_currency, to_currency)
            
            if rate_info:
                rate = rate_info['rate']
                updated_at = rate_info['updated_at']
                reverse_rate = rate_info['reverse_rate']
                
                print("\nКурс обмена:")
                print(f"   {from_currency} → {to_currency}: {rate:.6f}")
                
                if reverse_rate:
                    print(f"   {to_currency} → {from_currency}: {reverse_rate:.6f}")
                
                if updated_at:
                    formatted_time = format_datetime(updated_at)
                    print(f"   Обновлено: {formatted_time}")
                
                print(f"\nПример: 100 {from_currency} = {100 * rate:.2f} {to_currency}")
                
            else:
                print(f"Курс {from_currency}→{to_currency} недоступен")
                print("Повторите попытку позже")
                
        except CurrencyNotFoundError as e:
            print(f"{e}")
            print("Используйте 'list-currencies' для просмотра поддерживаемых валют")
        except ApiRequestError as e:
            print(f"{e}")
            print("Сервер курсов валют временно недоступен")
            print("Проверьте подключение к интернету и повторите попытку")
        except ExchangeRateUnavailableError as e:
            print(f"{e}")
            print("Курс для данной валютной пары временно недоступен")
            print("Попробуйте другую валютную пару или повторите позже")
    
    def list_currencies(self):
        try:
            supported_currencies = CurrencyRegistry.get_supported_currencies()
            
            table = PrettyTable()
            table.field_names = ["Код", "Название", "Тип", "Доп. информация"]
            table.align = "l"
            
            for code, data in supported_currencies.items():
                CurrencyRegistry.get_currency(code)
                if data["type"] == "fiat":
                    info = f"Страна: {data['issuing_country']}"
                else:
                    info = f"Алгоритм: {data['algorithm']}"
                
                table.add_row([code, data["name"], data["type"].upper(), info])
            
            print("\nПоддерживаемые валюты:")
            print(table)
            print(f"\nВсего валют: {len(supported_currencies)}")
            
        except Exception as e:
            print(f"Ошибка при получении списка валют: {e}")
