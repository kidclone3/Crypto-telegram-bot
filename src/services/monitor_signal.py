import asyncio
from motor.motor_asyncio import AsyncIOMotorDatabase
from telethon import TelegramClient

from src.services.MultiKernelRegression import apply_multi_kernel_regression
from src.services.price_bot import CryptoPriceBot


class SignalService:
    def __init__(self, db: AsyncIOMotorDatabase, client: TelegramClient):
        self.db = db
        self.client = client
        self.is_running = False
        self.user_last_alert = {}

    async def get_all_monitors(self, chat_id) -> list[dict]:
        query = await self.db.signals.find_one({"chat_id": chat_id})
        if query:
            return query.get("data", [])
        return []

    @classmethod
    async def add_monitor(cls, db, chat_id: int, symbols: list[str], price: float):
        # find if the user already has a monitor for the symbol
        # alerts has 2 fields: chat_id and data
        monitor = await db.signals.find_one({"chat_id": chat_id})

        if not monitor:
            monitor = {"chat_id": chat_id, "data": []}
        monitor["data"] = list(set(monitor["data"] + symbols))

        await db.signals.update_one(
            {"chat_id": chat_id}, {"$set": monitor}, upsert=True
        )
        return len(monitor["data"])

    @classmethod
    async def delete_monitor(cls, db, chat_id: int, id: int):
        list_monitors = await db.signals.find_one({"chat_id": chat_id})
        if not list_monitors:
            return False

        if id < 1 or id > len(list_monitors["data"]):
            return False

        list_monitors["data"].pop(id - 1)

        await db.signals.update_one({"chat_id": chat_id}, {"$set": list_monitors})

        return True

    async def check_alerts(self):
        while self.is_running:
            all_users = await self.db.signals.distinct("chat_id")
            price_bot = CryptoPriceBot()
            for user in all_users:
                alerts = await self.get_all_monitors(user)
                message_list = []
                for symbol in alerts:
                    for timeframe in ["2h", "4h", "1d"]:
                        try:
                            # Get current price
                            ticker_data, exchange = await price_bot.fetch_ohlcv_data(
                                symbol, timeframe=timeframe, limit=200
                            )

                            if ticker_data is None or ticker_data.empty:
                                continue

                            current_price = ticker_data.iloc[-1]["close"]
                            df = apply_multi_kernel_regression(
                                ticker_data, repaint=True
                            )
                            # Just get the closed candle
                            signal_up, signal_down = df.iloc[-2][
                                ["signal_up", "signal_down"]
                            ]
                            if signal_up:
                                # await self.client.send_message(
                                #     user,
                                #     f"📈 {exchange.capitalize()}: Signal for {symbol}: {current_price} in timeframe {timeframe} is up   ",
                                # )
                                message_list.append(
                                    f"📈 {exchange.capitalize()}: Signal for {symbol}: {current_price} in timeframe {timeframe} is up"
                                )
                            elif signal_down:
                                # await self.client.send_message(
                                #     user,
                                #     f"📉 {exchange.capitalize()}: Signal for {symbol}: {current_price} in timeframe {timeframe} is down   ",
                                # )
                                message_list.append(
                                    f"📉 {exchange.capitalize()}: Signal for {symbol}: {current_price} in timeframe {timeframe} is down"
                                )

                        except Exception as e:
                            print(f"Error checking alerts: {str(e)}")
                            await self.client.send_message(
                                user,
                                f"Error checking alerts for {symbol} in timeframe {timeframe}",
                            )
                await self.client.send_message(user, "\n".join(message_list))

            await price_bot.close()
            await asyncio.sleep(60 * 30)  # 30 minutes

    async def start_monitoring(self):
        self.is_running = True
        await self.check_alerts()

    async def stop_monitoring(self):
        self.is_running = False


if __name__ == "__main__":
    asyncio.run(SignalService().check_alerts())
