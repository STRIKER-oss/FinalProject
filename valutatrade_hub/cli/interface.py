"""Командный интерфейс приложения."""
import sys
import getpass
import argparse
from prettytable import PrettyTable
from ..core.usecases import UserManager, PortfolioManager, CurrencyManager
from ..core.exceptions import (
    InsufficientFundsError, CurrencyNotFoundError, ApiRequestError,
    UserNotFoundError, UserAlreadyExistsError, InvalidPasswordError,
    WalletNotFoundError, InvalidAmountError, ExchangeRateUnavailableError
)
from ..core.utils import validate_currency_code, validate_amount, format_datetime
from ..core.currencies import CurrencyRegistry
from ..infra.settings import settings
from ..logging_config import get_logger

logger = get_logger(__name__)


class CLIInterface:
    """Класс для взаимодействия с пользователем через CLI."""
    
    def __init__(self):
        self.user_manager = UserManager()
        self.currency_manager = CurrencyManager()
        self.portfolio_manager = PortfolioManager(user_manager=self.user_manager)
        self.current_user = None
    
    def print_help(self):
        """Вывод справки по командам."""
        print("\n=== Valutatrade Hub - Доступные команды ===")
        print("register --username <name> --password <pass>  - Регистрация")
        print("login --username <name> --password <pass>     - Вход в систему")
        print("show-portfolio [--base <curr>]                - Показать портфель")
        print("buy --currency <curr> --amount <num>          - Купить валюту")
        print("sell --currency <curr> --amount <num>         - Продать валюту")
        print("get-rate --from <curr> --to <curr>            - Получить курс")
        print("list-currencies                               - Список валют")
        print("help                                          - Показать справку")
        print("exit                                          - Выйти")
        print("\nПримеры:")
        print("  buy --currency EUR --amount 100")
        print("  sell --currency BTC --amount 0.5")
        print("  get-rate --from USD --to EUR")
        print("  show-portfolio --base EUR")
    
    def run(self):
        """Запуск интерфейса."""
        print("Добро пожаловать в Valutatrade Hub!")
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
                elif user_input == "":
                    continue
                else:
                    self.parse_command(user_input)
            
            except KeyboardInterrupt:
                print("\n\nДо свидания!")
                break
            except Exception as e:
                print(f"Ошибка: {e}")
                logger.error(f"CLI error: {e}", exc_info=True)
    
    def parse_command(self, command_line: str):
        """Парсинг командной строки."""
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
    
    def handle_show_portfolio(self, args):
        """Обработка команды show-portfolio."""
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
            logger.error(f"Show portfolio error: {e}")
    
    def show_portfolio(self, base_currency: str = None):
        """Показать портфель и балансы."""
        if not self.current_user:
            print("Ошибка: Сначала выполните вход в систему (login)")
            return
        
        # Используем базовую валюту из настроек если не указана
        if base_currency is None:
            base_currency = settings.get_default_base_currency()
        
        base_currency = base_currency.upper()
        
        # Проверяем базовую валюту через иерархию валют
        try:
            currency_obj = CurrencyRegistry.get_currency(base_currency)
        except CurrencyNotFoundError:
            print(f"Ошибка: Неизвестная базовая валюта '{base_currency}'")
            print("Используйте 'list-currencies' для просмотра поддерживаемых валют")
            return
        
        # Загружаем портфель пользователя
        try:
            portfolio = self.portfolio_manager.get_portfolio(self.current_user.user_id)
            wallets = portfolio.wallets
        except Exception as e:
            print(f"Ошибка при загрузке портфеля: {e}")
            return
        
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
            
            # Получаем курс конвертации в базовую валюту
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
            
            # Добавляем строку в таблицу
            table.add_row([
                f"{currency_code}",
                f"{balance:.4f}",
                f"{rate_info}",
                f"{value_in_base:.2f} {base_currency}"
            ])
        
        # Выводим таблицу
        print(table)
        
        # Показываем итоговую сумму
        print("-" * 60)
        print(f"ИТОГО: {total_value:,.2f} {base_currency}")
    
    def handle_register(self, args):
        """Обработка команды register."""
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
            logger.error(f"Registration error: {e}")
    
    def register(self, username: str, password: str):
        """Регистрация пользователя."""
        try:
            if self.user_manager.register_user(username, password):
                user = self.user_manager.find_user_by_username(username)
                print(f"Пользователь '{username}' успешно зарегистрирован (id={user.user_id})")
                print(f"На ваш счет зачислено 10,000 USD стартового капитала")
                print(f"Теперь вы можете войти: login --username {username} --password [ваш пароль]")
        except UserAlreadyExistsError as e:
            print(f"{e}")
        except ValueError as e:
            print(f"Ошибка валидации: {e}")
        except Exception as e:
            print(f"Ошибка при регистрации: {e}")
    
    def handle_login(self, args):
        """Обработка команды login."""
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
            logger.error(f"Login error: {e}")
    
    def login(self, username: str, password: str):
        """Вход пользователя."""
        try:
            if self.user_manager.authenticate_user(username, password):
                self.current_user = self.user_manager.find_user_by_username(username)
                print(f"Вы успешно вошли как '{username}'")
                print(f"Для просмотра портфеля используйте: show-portfolio")
        except (UserNotFoundError, InvalidPasswordError) as e:
            print(f"{e}")
        except Exception as e:
            print(f"Ошибка при входе: {e}")
    
    def handle_buy(self, args):
        """Обработка команды buy."""
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
            logger.error(f"Buy error: {e}")
    
    def buy_currency(self, currency: str, amount: float):
        """Купить валюту."""
        currency = currency.upper()
        
        try:
            # Получаем информацию о валюте для красивого вывода
            currency_obj = CurrencyRegistry.get_currency(currency)
            
            # Получаем текущий портфель пользователя до операции
            portfolio = self.portfolio_manager.get_portfolio(self.current_user.user_id)
            old_balance = portfolio.get_balance(currency)
            old_usd_balance = portfolio.get_balance("USD")
            
            # Получаем текущий курс для информации
            exchange_rate = self.currency_manager.get_rate("USD", currency)
            purchase_cost = amount * exchange_rate
            
            print(f"Покупка {amount:.4f} {currency}...")
            print(f"Стоимость покупки: {purchase_cost:.2f} USD")
            print(f"Курс: 1 {currency} = {exchange_rate:.2f} USD")
            
            # Выполняем покупку
            if self.portfolio_manager.buy_currency(self.current_user.user_id, currency, amount):
                # Получаем новый баланс после покупки
                new_balance = portfolio.get_balance(currency)
                new_usd_balance = portfolio.get_balance("USD")
                
                print(f"Покупка выполнена успешно!")
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
        """Обработка команды sell."""
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
            logger.error(f"Sell error: {e}")
    
    def sell_currency(self, currency: str, amount: float):
        """Продать валюту."""
        currency = currency.upper()
        
        try:
            # Получаем информацию о валюте для красивого вывода
            currency_obj = CurrencyRegistry.get_currency(currency)
            
            # Получаем текущий портфель пользователя до операции
            portfolio = self.portfolio_manager.get_portfolio(self.current_user.user_id)
            old_balance = portfolio.get_balance(currency)
            old_usd_balance = portfolio.get_balance("USD")
            
            # Получаем текущий курс для информации
            exchange_rate = self.currency_manager.get_rate(currency, "USD")
            usd_revenue = amount * exchange_rate
            
            print(f"Продажа {amount:.4f} {currency}...")
            print(f"Ожидаемая выручка: {usd_revenue:.2f} USD")
            print(f"Курс: 1 {currency} = {exchange_rate:.2f} USD")
            
            # Проверяем наличие достаточного количества валюты
            if old_balance < amount:
                raise InsufficientFundsError(
                    currency_code=currency,
                    available=old_balance,
                    required=amount
                )
            
            # Выполняем продажу
            if self.portfolio_manager.sell_currency(self.current_user.user_id, currency, amount):
                # Получаем новый баланс после продажи
                new_balance = portfolio.get_balance(currency)
                new_usd_balance = portfolio.get_balance("USD")
                
                print(f"Продажа выполнена успешно!")
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
        """Обработка команды get-rate."""
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
            logger.error(f"Get rate error: {e}")
    
    def get_rate(self, from_currency: str, to_currency: str):
        """Получить курс валюты."""
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()
        
        try:
            # Получаем информацию о валютах для красивого вывода
            from_curr_obj = CurrencyRegistry.get_currency(from_currency)
            to_curr_obj = CurrencyRegistry.get_currency(to_currency)
            
            # Получаем курс с информацией
            rate_info = self.currency_manager.get_rate_with_info(from_currency, to_currency)
            
            if rate_info:
                rate = rate_info['rate']
                updated_at = rate_info['updated_at']
                reverse_rate = rate_info['reverse_rate']
                
                # Форматируем вывод
                print(f"\nКурс обмена:")
                print(f"   {from_currency} → {to_currency}: {rate:.6f}")
                
                if reverse_rate:
                    print(f"   {to_currency} → {from_currency}: {reverse_rate:.6f}")
                
                if updated_at:
                    formatted_time = format_datetime(updated_at)
                    print(f"   Обновлено: {formatted_time}")
                
                # Показываем пример конвертации
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
        """Показать список поддерживаемых валют."""
        try:
            supported_currencies = CurrencyRegistry.get_supported_currencies()
            
            table = PrettyTable()
            table.field_names = ["Код", "Название", "Тип", "Доп. информация"]
            table.align = "l"
            
            for code, data in supported_currencies.items():
                currency = CurrencyRegistry.get_currency(code)
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
            logger.error(f"List currencies error: {e}")
