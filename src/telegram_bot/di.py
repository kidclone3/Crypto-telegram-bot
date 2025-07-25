"""
Dependency Injection Container for telegram-crypto-bot.

This container provides a centralized place to instantiate and retrieve core components,
such as the Telegram bot client, database client, and monitoring services.

Usage:
    from telegram_bot.di import container
    monitor_service = container.monitor_service
    signal_service = container.signal_service
"""

from telegram_bot.bot.telegram_bot import bot, db, initialize_and_start_bot
from telegram_bot.services.monitor_service import MonitorService
from telegram_bot.services.monitor_signal import SignalService
from telegram_bot.utils.logger import logger


class Container:
    def __init__(self):
        self._bot = bot
        self._db = db
        self._monitor_service = None
        self._signal_service = None

    @property
    def telegram_bot(self):
        return self._bot

    @property
    def db_client(self):
        return self._db

    @property
    def initialize_bot(self):
        return initialize_and_start_bot

    @property
    def monitor_service(self):
        if self._monitor_service is None:
            # Instantiate MonitorService with dependency injection
            self._monitor_service = MonitorService(
                self.db_client, self.telegram_bot
            )
        return self._monitor_service

    @property
    def signal_service(self):
        if self._signal_service is None:
            # Instantiate SignalService with dependency injection
            self._signal_service = SignalService(
                self.db_client, self.telegram_bot
            )
        return self._signal_service


# Instantiate the container as a singleton for use across the project
container = Container()
