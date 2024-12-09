import pathlib
import ccxt.async_support as ccxt
import pandas as pd
import os
import dotenv
import asyncio

from telegram import Update
from telegram_handler import TelegramHandler

dotenv.load_dotenv()

mock_wallet = {}


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


def initialize_bot():
    """Initialize bot with required data and start monitoring"""
    TELEGRAM_TOKEN = os.environ.get("YOUR_BOT_TOKEN")
    path = pathlib.Path("top_200_currencies.csv")

    if path.exists():
        data = pd.read_csv(path)
    else:
        data = asyncio.run(get_top_marketcap_currencies(200))
        data.to_csv("top_200_currencies.csv", index=True)

    SYMBOLS = data["symbol"].tolist()

    # Create alert_list.txt if it doesn't exist
    if not pathlib.Path("alert_list.txt").exists():
        with open("alert_list.txt", "w") as f:
            pass

    # Initialize and run the telegram handler
    telegram_handler = TelegramHandler(TELEGRAM_TOKEN, SYMBOLS)
    telegram_handler.run()


if __name__ == "__main__":
    try:
        initialize_bot()
    except KeyboardInterrupt:
        print("\nBot stopped by admin")
    except Exception as e:
        print(f"Error running bot: {str(e)}")
