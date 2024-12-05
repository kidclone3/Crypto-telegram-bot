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
import dotenv
import asyncio
from utils import time_it

dotenv.load_dotenv()

mock_wallet = {}


class CryptoPriceBot:
    def __init__(self, exchange_id: str = "binance"):
        self.exchange = getattr(ccxt, exchange_id)(
            {
                "enableRateLimit": True,
            }
        )

    async def fetch_single_price(
        self, symbol: str, timeframe: str, threshold: float
    ) -> tuple[str, float] | None:
        try:
            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=5)

            if len(ohlcv) >= 2:
                prev_close = ohlcv[-2][4]
                current_close = ohlcv[-1][4]
                pct_change = ((current_close - prev_close) / prev_close) * 100
                if abs(pct_change) >= threshold:
                    return symbol, round(pct_change, 2)
            return None
        except Exception as e:
            print(f"Error fetching data for {symbol}: {str(e)}")
            return None

    async def fetch_price_data(
        self, symbols: List[str], timeframe: str = "1h", threshold: float = 1.0
    ) -> Dict[str, float]:
        try:
            tasks = [
                self.fetch_single_price(symbol, timeframe, threshold)
                for symbol in symbols
            ]
            results = await asyncio.gather(*tasks)

            price_changes = {
                symbol: change
                for result in results
                if result is not None
                for symbol, change in [result]
            }

            top_10_price_changes = dict(
                sorted(
                    price_changes.items(), key=lambda item: abs(item[1]), reverse=True
                )[:10]
            )

            await self.exchange.close()
            return top_10_price_changes
        except Exception as e:
            print(f"Error fetching price data: {str(e)}")
            await self.exchange.close()
            raise


class TelegramHandler:
    def __init__(self, token: str, symbols: List[str]):
        self.application = Application.builder().token(token).build()
        self.symbols = symbols
        self.timeframe = "15m"
        self.threshold = 1.0

        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(
            CommandHandler(["p", "prices"], self.prices_command)
        )
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("ping", self.ping_command))

    async def start_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        welcome_msg = (
            "👋 Welcome to the Crypto Price Bot!\n\n"
            "Available commands:\n"
            "/p or /prices - Get current price changes\n"
            "/p 15m 1 - Filter price changes by timeframe and percentage (unit %)\n"
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
            "/p 15m 0.01 - Filter price changes by timeframe and percentage\n"
            "/help - Show this help message\n\n"
            "The bot monitors the following pairs:\n"
            f"{', '.join(self.symbols)}"
        )
        await update.message.reply_text(help_msg)

    async def prices_command(
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
            price_changes = await price_bot.fetch_price_data(
                self.symbols, _timeframe, threshold=_threshold
            )
            print(price_changes)

            if not price_changes:
                await update.message.reply_text("⚠️ Unable to fetch price data.")
                return

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
            message = f"🔄 Price Changes ({self.timeframe})\n📅 {timestamp}\n\n"
            for symbol, change in price_changes.items():
                emoji = "🟢" if change >= 0 else "🔴"
                message += f"{emoji} {symbol}: {change:+.2f}%\n"

            await update.message.reply_text(message)
            end_time = time.time()
            print(f"Time taken: {end_time - start_time}")

        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def ping_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🏓 Pong!")

    def run(self):
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)


async def get_top_marketcap_currencies(limit: int = 100) -> pd.DataFrame:
    exchange = ccxt.binance({"enableRateLimit": True})
    try:
        tickers = await exchange.fetch_tickers()
        market_data = []
        for symbol, ticker in tickers.items():
            if symbol.endswith("/USDT"):
                if "info" in ticker and ticker.get("quoteVolume"):
                    market_data.append(
                        {
                            "symbol": symbol,
                            "price": ticker.get("last", 0),
                            "volume_24h": float(ticker.get("quoteVolume", 0)),
                            "market_cap": float(ticker.get("quoteVolume", 0))
                            * ticker.get("last", 0),
                            "change_24h": ticker.get("percentage", 0),
                        }
                    )

        df = pd.DataFrame(market_data)
        df = df.sort_values("market_cap", ascending=False).reset_index(drop=True)
        df["price"] = df["price"].map("${:,.2f}".format)
        df["volume_24h"] = df["volume_24h"].map("${:,.0f}".format)
        df["market_cap"] = df["market_cap"].map("${:,.0f}".format)
        df["change_24h"] = df["change_24h"].map("{:+.2f}%".format)
        await exchange.close()
        return df.head(limit)
    except Exception as e:
        print(f"Error fetching market data: {str(e)}")
        await exchange.close()
        return pd.DataFrame()


if __name__ == "__main__":
    TELEGRAM_TOKEN = os.environ.get("YOUR_BOT_TOKEN")
    path = pathlib.Path("top_200_currencies.csv")

    if path.exists():
        data = pd.read_csv(path)
    else:
        data = asyncio.run(get_top_marketcap_currencies(200))
        data.to_csv("top_200_currencies.csv", index=True)

    SYMBOLS = data["symbol"].tolist()
    telegram_handler = TelegramHandler(TELEGRAM_TOKEN, SYMBOLS)
    telegram_handler.run()
