import pathlib
from typing import List, Dict
import ccxt.async_support as ccxt
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import time
import io
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os
import asyncio
from utils import symbol_complete, time_it, format_price_message
import threading
from queue import Queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from crypto_price_bot import CryptoPriceBot


class TelegramHandler:
    def __init__(self, token: str, symbols: List[str]):
        self.application = Application.builder().token(token).build()
        self.symbols = symbols
        self.timeframe = "15m"
        self.threshold = 1.0

        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler(["p", "price"], self.price_command))
        self.application.add_handler(
            CommandHandler(["f", "filter"], self.filter_command)
        )
        self.application.add_handler(CommandHandler(["c", "chart"], self.chart_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("ping", self.ping_command))

    async def ping_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🏓 Pong!")

    async def start_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        welcome_msg = (
            "👋 Welcome to the Crypto Price Bot!\n\n"
            "Available commands:\n"
            "/p or /prices - Get current price\n"
            "\t E.g: /p BTC\n"
            "/filter - Filter price changes by timeframe and percentage\n"
            "\t E.g: /f 15m 1 \n"
            "/c or /chart - Get price chart for a cryptocurrency\n"
            "/h or /help - Show this help message\n"
            "/ping - Check if the bot is online"
        )
        await update.message.reply_text(welcome_msg)

    async def help_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        help_msg = (
            "🤖 Crypto Price Bot Commands:\n\n"
            "/p or /prices - Get 1h price changes for monitored cryptocurrencies\n"
            "/f 15m 1 - Filter price changes by timeframe and percentage\n"
            "/c or /chart - Get price chart for a cryptocurrency\n"
            "/help - Show this help message\n\n"
            "The bot monitors the following pairs:\n"
            "{}".format("\n ".join(self.symbols))
        )
        await update.message.reply_text(help_msg)

    async def price_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle the /price command
        Usage: /price <symbol> (e.g., /price BTC/USDT)
        """
        try:
            # Check if symbol is provided
            if not context.args:
                await update.message.reply_text(
                    "⚠️ Please provide a symbol. Example: /price BTC/USDT\n"
                    f"Available symbols:\n{', '.join(self.symbols[:10])}..."
                )
                return

            # Get the symbol and ensure it's uppercase
            symbol = symbol_complete(context.args[0].upper())

            # Check if symbol is supported
            if symbol not in self.symbols:
                await update.message.reply_text(
                    f"⚠️ Symbol {symbol} not found. Please choose from supported symbols.\n"
                    f"Example symbols:\n{', '.join(self.symbols[:5])}..."
                )
                return

            await update.message.reply_text(f"📊 Fetching price data for {symbol}...")

            # Create a new bot instance for this request
            price_bot = CryptoPriceBot()
            ticker_data = await price_bot.fetch_latest_price(symbol)
            await price_bot.close()

            if not ticker_data:
                await update.message.reply_text(f"❌ Unable to fetch data for {symbol}")
                return

            # Format the message
            message = format_price_message(ticker_data)
            await update.message.reply_text(message)
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def filter_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        await update.message.reply_text("📊 Fetching price data...")
        try:
            start_time = time.time()
            price_bot = CryptoPriceBot()
            _timeframe = self.timeframe
            _threshold = self.threshold
            if len(context.args) == 2:
                _timeframe = context.args[0]
                _threshold = float(context.args[1])
            tasks = [
                price_bot.fetch_price_changes(symbol, _timeframe, threshold=_threshold)
                for symbol in self.symbols
            ]
            price_changes = await asyncio.gather(*tasks)
            await price_bot.close()

            if not price_changes:
                await update.message.reply_text("⚠️ Unable to fetch price data.")
                return

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
            message = f"🔄 Price Changes ({self.timeframe})\n📅 {timestamp}\n\n"
            for data in price_changes:
                if not data:
                    continue
                emoji = "🟢" if data["pct_change"] >= 0 else "🔴"
                message += f"""{emoji} {data["symbol"]}: {data["pct_change"]:+.2f}%\n"""

            await update.message.reply_text(message)
            end_time = time.time()
            print(f"Time taken: {end_time - start_time}")

        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def chart_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle the /chart command
        Usage: /chart <symbol> [timeframe]
        Example: /chart BTC/USDT 4h
        """
        try:
            if not context.args:
                await update.message.reply_text(
                    "⚠️ Please provide a symbol. Example: /chart BTC/USDT 4h\n"
                    "Available timeframes: 1m, 5m, 15m, 1h, 4h, 1d\n"
                    f"Available symbols:\n{', '.join(self.symbols[:10])}..."
                )
                return

            # Parse arguments
            symbol = symbol_complete(context.args[0].upper())
            timeframe = context.args[1].lower() if len(context.args) > 1 else "1h"

            # Validate timeframe
            valid_timeframes = ["1m", "5m", "15m", "1h", "4h", "1d"]
            if timeframe not in valid_timeframes:
                await update.message.reply_text(
                    f"⚠️ Invalid timeframe. Please choose from: {', '.join(valid_timeframes)}"
                )
                return

            # Validate symbol
            if symbol not in self.symbols:
                await update.message.reply_text(
                    f"⚠️ Symbol {symbol} not found. Please choose from supported symbols.\n"
                    f"Example symbols:\n{', '.join(self.symbols[:5])}..."
                )
                return

            # Send loading message
            msg = await update.message.reply_text(
                f"📊 Generating {timeframe} chart for {symbol}..."
            )

            # Get candle data and create chart
            price_bot = CryptoPriceBot()
            df = await price_bot.fetch_ohlcv_data(symbol, timeframe)
            await price_bot.close()

            if df is None or df.empty:
                await msg.edit_text(f"❌ Unable to fetch data for {symbol}")
                return

            # Calculate some basic statistics
            change_pct = ((df["close"][-1] - df["close"][0]) / df["close"][0]) * 100
            high = df["high"].max()
            low = df["low"].min()
            volume = df["volume"].sum()

            # Create and send chart
            chart_buf = await price_bot.generate_chart(df, symbol, timeframe)
            if chart_buf is None:
                await msg.edit_text("❌ Error generating chart")
                return

            # Format caption
            caption = (
                f"📈 {symbol} {timeframe} Chart\n"
                f"Period: {df.index[0].strftime('%Y-%m-%d %H:%M')} - {df.index[-1].strftime('%Y-%m-%d %H:%M')}\n"
                f"Price: ${df['close'][-1]:,.2f}\n"
                f"Change: {change_pct:+.2f}% {'🟢' if change_pct >= 0 else '🔴'}\n"
                f"High: ${high:,.2f}\n"
                f"Low: ${low:,.2f}\n"
                f"Volume: ${volume:,.2f}"
            )

            # Delete loading message and send chart
            await msg.delete()
            await update.message.reply_photo(chart_buf, caption=caption)

        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")

    def run(self):
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)
