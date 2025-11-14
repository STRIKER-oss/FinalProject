#!/usr/bin/env python3
"""Главный модуль приложения Valutatrade Hub."""

from valutatrade_hub.cli.interface import CLIInterface
from valutatrade_hub.logging_config import setup_logging


def main():
    """Главная функция приложения."""
    # Настройка логирования
    setup_logging()
    
    cli = CLIInterface()
    cli.run()


if __name__ == "__main__":
    main()
