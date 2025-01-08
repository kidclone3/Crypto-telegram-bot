import asyncio
from collections import defaultdict
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorDatabase
from telethon import TelegramClient

from src.services.price_bot import CryptoPriceBot


class MonitorService:
    def __init__(self, db: AsyncIOMotorDatabase, client: TelegramClient):
        self.db = db
        self.client = client
        self.is_running = False
        self.user_last_alert = {}

    async def get_all_monitors(self, chat_id) -> list[dict]:
        query = await self.db.alerts.find_one({"chat_id": chat_id})
        if query:
            return query.get("data", [])
        return []

    @classmethod
    async def add_monitor(cls, db, chat_id: int, data: dict):
        # find if the user already has a monitor for the symbol
        # alerts has 2 fields: chat_id and data
        monitor = await db.alerts.find_one({"chat_id": chat_id})

        if not monitor:
            monitor = {"chat_id": chat_id, "data": []}
        symbol = data.get("symbol")
        price = data.get("price")
        msg = data.get("msg", None)
        monitor["data"].append({"symbol": symbol, "price": price, "msg": msg})
        await db.alerts.update_one({"chat_id": chat_id}, {"$set": monitor}, upsert=True)
        return len(monitor["data"])

    @classmethod
    async def update_monitor(cls, db, chat_id: int, data: dict):
        # find if the user already has a monitor for the symbol
        try:
            monitor = await db.alerts.find_one({"chat_id": chat_id})

            if not monitor:
                monitor = {"chat_id": chat_id, "data": []}
            alert_id = data["id"]
            price = data["price"]
            msg = data["msg"]
            monitor["data"][alert_id - 1]["price"] = price
            monitor["data"][alert_id - 1]["msg"] = msg
            await db.alerts.update_one(
                {"chat_id": chat_id}, {"$set": monitor}, upsert=True
            )
            return monitor["data"][alert_id - 1]["symbol"]
        except Exception as e:
            print(f"Error updating monitor {str(e)}")
            return None

    @classmethod
    async def delete_monitor(cls, db, chat_id: int, id: int):
        list_monitors = await db.alerts.find_one({"chat_id": chat_id})
        if not list_monitors:
            return False

        if id < 1 or id > len(list_monitors["data"]):
            return False

        list_monitors["data"].pop(id - 1)

        await db.alerts.update_one({"chat_id": chat_id}, {"$set": list_monitors})

        return True

    async def check_alerts(self):
        while self.is_running:
            all_users = await self.db.alerts.distinct("chat_id")
            price_bot = CryptoPriceBot()
            for user in all_users:
                user_config = await self.db.config.find_one({"chat_id": user})

                price_threshold = user_config["price_threshold"]
                is_alert_on = user_config["is_alert"] == "on"
                alert_interval = user_config["alert_interval"]
                # Skip if alerts are turned off for this user
                if not is_alert_on:
                    continue
                current_time = datetime.now().timestamp()
                last_alert_time = self.user_last_alert.get(user, 0)
                if current_time - last_alert_time < alert_interval * 60:
                    continue
                alerts = await self.get_all_monitors(user)
                alerts_dict = defaultdict(list)
                for alert in alerts:
                    alerts_dict[alert["symbol"]].append(
                        (float(alert.get("price")), alert.get("msg"))
                    )

                for symbol, values in alerts_dict.items():
                    try:
                        # Get current price
                        ticker_data = await price_bot.fetch_timeframe_change(
                            symbol, "1m"
                        )
                        if not ticker_data:
                            continue
                        current_price = ticker_data["current_price"]
                        for target_price, msg in values:
                            # Calculate price difference percentage
                            price_diff_pct = (
                                abs(current_price - target_price) / target_price * 100
                            )
                            # If price is within threshold, send alert
                            if price_diff_pct <= price_threshold:
                                alert_message = (
                                    f"🚨 Price Alert!\n"
                                    f"Exchange: {ticker_data['exchange']}\n"
                                    f"Symbol: {symbol}\n"
                                    f"Target: ${target_price:,.4f}\n"
                                    f"Current: ${current_price:,.4f}\n"
                                    f"Difference: {price_diff_pct:.4f}%\n"
                                    f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                                    "\n"
                                    f"Message: {msg}"
                                )
                                # Send alert to all active chats
                                await self.client.send_message(
                                    user, message=alert_message
                                )
                    except Exception as e:
                        print(f"Error checking alerts: {str(e)}")
            await price_bot.close()
            await asyncio.sleep(60)

    async def start_monitoring(self):
        self.is_running = True
        await self.check_alerts()

    async def stop_monitoring(self):
        self.is_running = False
