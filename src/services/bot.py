import asyncio
import copy
from datetime import datetime
import json
import time
import logging
import os
from functools import lru_cache
from tabulate import tabulate
from telethon import Button, TelegramClient, events
from telethon.types import DocumentAttributeFilename
import pandas as pd

from src.services.economic_calendar_table import final_table
from src.services.monitor_service import MonitorService
from src.services.indicators import quant_agent
from src.services.monitor_signal import SignalService
from src.services.price_bot import CryptoPriceBot
from src.core.config import settings
from src.utils.tools import format_price_message, symbol_complete
from src.core.db import motor_client
from src.utils.logger import logger

@lru_cache(maxsize=1)
def setup_logger(name, file_path=None):
    if file_path is None:
        file_path = os.path.join(
            os.environ.get("LOG_FOLDER", "."),
            "%s_%s.log" % (name, datetime.now().strftime("%Y-%m-%d")),
        )
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(file_path)
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(filename)s line %(lineno)d: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Add stdout handler
    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(formatter)
    stdout_handler.setLevel(logging.INFO)
    logger.addHandler(stdout_handler)
    return logger

logger = setup_logger("telegram_bot")

START_MSG = (
    "👋 Welcome to the Crypto Price Bot!\n\n"
    "Available commands:\n"
    "/start - Show this welcome message\n"
    "/help - Show this help message\n"
    "/ping - Check if the bot is online\n\n"
    "Price & Alerts:\n"
    "/a or /alert - Manage price alerts\n"
    "\t E.g: /a BTC 1000000 - Set alert on BTC at 100k\n"
    "\t /a - List all active alerts\n"
    "/dela or /delete_alert - Delete a price alert\n"
    "\t E.g: /dela 1 - Delete alert with ID 1\n"
    "/p or /price - Get current price\n"
    "\t E.g: /p BTC/USDT\n\n"
    "Technical Analysis:\n"
    "/f or /filter - Filter price changes by timeframe and percentage\n"
    "\t E.g: /f 15m 1 - Show coins with 1% change in 15 minutes\n"
    "/c or /chart - Get price chart for a cryptocurrency\n"
    "\t E.g: /c BTC/USDT 4h - Get 4-hour chart\n"
    "\t Available timeframes: 1m, 5m, 15m, 1h, 4h, 1d\n"
    "/s or /signal - Get trading signal for a cryptocurrency\n"
    "\t E.g: /s BTC 1h - Get 1-hour trading signals\n\n"
    "Market Monitoring:\n"
    "/mon or /monitor - Manage symbol monitoring\n"
    "\t E.g: /mon BTC ETH - Monitor BTC and ETH\n"
    "\t /mon - List all monitored symbols\n"
    "/delmon or /delete_monitor - Delete a monitor\n"
    "\t E.g: /delmon 1 - Delete monitor with ID 1\n"
    "/calendar - Get economic calendar events\n"
    "/llm - Send a prompt to the LLM\n"
    "\t E.g: /llm What's the current price of Bitcoin?\n\n"
    "Configuration:\n"
    "/config - View or update bot settings\n"
    "\t E.g: /config is_alert on/off\n"
    "\t E.g: /config price_threshold 0.01\n"
    "\t E.g: /config alert_interval 1\n"
    "\t E.g: /config is_future on/off"
)

DEFAULT_CONFIG = {
    "is_alert": "off",
    "price_threshold": 0.01,
    "alert_interval": 1,
    "is_future": "off",
}

PATTERN_TWO_ARGS = r"\s+([a-zA-Z]+)(?:\s+(\d+[mh]))?$"

loop = asyncio.get_event_loop()

bot: TelegramClient = TelegramClient(
    "bot", settings.api_id, settings.api_hash, timeout=5, auto_reconnect=True, loop=loop
).start(bot_token=settings.bot_token)

db = motor_client["crypto"]


# TODO: Should we use pydantic for this?
async def get_config(chat_id: int) -> dict:
    config = await db.config.find_one({"chat_id": chat_id})
    if not config:
        await db.config.insert_one({"chat_id": chat_id, **DEFAULT_CONFIG})
        return await db.config.find_one({"chat_id": chat_id})
    return config


@bot.on(events.NewMessage(pattern=r"^\/start$"))
async def send_welcome(event):
    logger.info(f"Received /start command from chat_id: {event.chat_id}")
    try:
        # add a run loop to monitor price
        chat_id = event.chat_id
        config = await db.config.find_one({"chat_id": chat_id})
        if not config:
            logger.info(f"Creating new config for chat_id: {chat_id}")
            await db.config.insert_one({"chat_id": chat_id, **DEFAULT_CONFIG})
        logger.info(f"Sent welcome message to chat_id: {event.chat_id}")
        await event.reply(START_MSG)
    except Exception as e:
        logger.error(f"Error in /start command for chat_id: {event.chat_id}: {str(e)}")
        await event.reply("❌ An error occurred. Please try again later.")


@bot.on(events.NewMessage(pattern=r"^\/help$"))
async def send_help(event):
    logger.info(f"Received /help command from chat_id: {event.chat_id}")
    try:
        await event.reply(START_MSG)
        logger.info(f"Sent help message to chat_id: {event.chat_id}")
    except Exception as e:
        logger.error(f"Error in /help command for chat_id: {event.chat_id}: {str(e)}")
        await event.reply("❌ An error occurred. Please try again later.")


@bot.on(events.NewMessage(pattern=r"^\/ping$"))
async def echo_all(event):
    logger.info(f"Received /ping command from chat_id: {event.chat_id}")
    try:
        await event.reply("pong")
        logger.info(f"Sent pong response to chat_id: {event.chat_id}")
    except Exception as e:
        logger.error(f"Error in /ping command for chat_id: {event.chat_id}: {str(e)}")
        await event.reply("❌ An error occurred. Please try again later.")


@bot.on(events.NewMessage(pattern=r"^\/config"))
async def config_command(event):
    logger.info(f"Received /config command from chat_id: {event.chat_id}")
    try:
        args = event.message.text.split()
        chat_id = event.chat_id
        config = await get_config(chat_id)

        if len(args) == 1:
            if not config:
                logger.warning(f"No configuration found for chat_id: {chat_id}")
                await event.reply("⚠️ No configuration found.")
                return
            else:
                print_config = copy.deepcopy(config)
                del print_config["_id"]
                del print_config["chat_id"]
                logger.info(f"Sent configuration to chat_id: {chat_id}")
                await event.reply(
                    f"🔧 Configuration for you:\n"
                    f"{json.dumps(print_config, indent=4, default=str)}"
                )
        elif len(args) == 3:
            config_key = args[1]
            config_value = args[2]

            if config_key not in config.keys():
                logger.warning(f"Invalid configuration key {config_key} for chat_id: {chat_id}")
                await event.reply("⚠️ Invalid configuration key.")
                return

            def validate_on_off(value: str):
                return value.lower() not in ["on", "off"]

            if config_key == "is_alert":
                if validate_on_off(config_value.lower()):
                    logger.warning(f"Invalid value for is_alert: {config_value} for chat_id: {chat_id}")
                    await event.reply("⚠️ Invalid value for is_alert. Use 'on' or 'off'.")
                    return
                config_value = config_value.lower()
            elif config_key == "is_future":
                if validate_on_off(config_value.lower()):
                    logger.warning(f"Invalid value for is_future: {config_value} for chat_id: {chat_id}")
                    await event.reply("⚠️ Invalid value for is_future. Use 'on' or 'off'.")
                    return
                config_value = config_value.lower()
            elif config_key == "price_threshold":
                config_value = float(config_value)
            elif config_key == "alert_interval":
                config_value = int(config_value)

            logger.info(f"Updating configuration for chat_id: {chat_id}, key: {config_key}, value: {config_value}")
            db.config.update_one(
                {"chat_id": chat_id},
                {"$set": {config_key: config_value}},
            )
            await event.reply(f"✅ Configuration updated: {config_key} = {config_value}")
    except Exception as e:
        logger.error(f"Error in /config command for chat_id: {event.chat_id}: {str(e)}")
        await event.reply("❌ An error occurred. Please try again later.")


@bot.on(events.NewMessage(pattern=r"^\/(?:a|alert)"))
async def add_alert(event):
    args = event.message.message.split(" ")
    chat_id = event.chat_id
    if len(args) == 1:
        logger.info(f"Fetching alerts for chat_id: {chat_id}")
        query = await db.alerts.find_one({"chat_id": chat_id})
        alerts = []
        if query:
            alerts = query.get("data", [])

        if not alerts:
            logger.info(f"No alerts found for chat_id: {chat_id}")
            await event.reply("🔕 No alerts set")
            return

        logger.info(f"Found {len(alerts)} alerts for chat_id: {chat_id}")
        table_header = ["ID", "Symbol", "Price ($)", "Message"]
        table_body = []
        for i, alert in enumerate(alerts):
            symbol, price, msg = (
                alert.get("symbol"),
                alert.get("price"),
                alert.get("msg", ""),
            )
            table_body.append([i + 1, symbol, f"${price}", msg])

        alert_table = tabulate(table_body, headers=table_header, tablefmt="pretty")
        await event.reply(f"🔔 Alerts:\n<pre>{alert_table}</pre>", parse_mode="HTML")
        return
    else:
        price = float(args[2])
        msg = " ".join(args[3:]) if len(args) > 3 else None
        if args[1].isnumeric():
            alert_id = int(args[1])
            logger.info(f"Updating alert {alert_id} for chat_id: {chat_id}")
            data = {"id": alert_id, "price": price, "msg": msg}
            symbol = await MonitorService.update_monitor(db, chat_id, data)
            if not symbol:
                logger.warning(f"Invalid alert ID {alert_id} for chat_id: {chat_id}")
                await event.reply("⚠️ Invalid alert ID")
                return
            logger.info(f"Successfully updated alert {alert_id} for {symbol}")
            await event.reply(
                f"✅ Alert ID {alert_id} of symbol {symbol} updated to ${price:,.3f}\n Message: {msg}"
            )
            return
        symbol = symbol_complete(args[1].upper())
        logger.info(f"Adding new alert for {symbol} at ${price:,.3f}")
        data = {
            "symbol": symbol,
            "price": price,
            "msg": msg,
        }
        added_id = await MonitorService.add_monitor(db, chat_id, data)
        logger.info(f"Successfully added alert {added_id} for {symbol}")
        await event.reply(
            f"✅ Alert {added_id} set for {symbol} at ${price:,.3f}\n Message: {msg}"
        )


@bot.on(events.NewMessage(pattern=r"^\/(?:dela|delete_alert)"))
async def delete_alert(event):
    args = event.message.text.split()
    if len(args) < 2:
        logger.warning("Delete alert command called without symbols")
        await event.reply(
            "⚠️ Please provide at least one symbol to delete.\n"
            "Usage: /dela <symbol1> [symbol2] [symbol3] ...\n"
            "Example: /dela ETH XRP WLD"
        )
        return

    chat_id = event.chat_id
    logger.info(f"Fetching alerts for deletion for chat_id: {chat_id}")
    query = await db.alerts.find_one({"chat_id": chat_id})
    alerts = query.get("data", [])

    if not alerts:
        logger.info(f"No alerts found for chat_id: {chat_id}")
        await event.reply("🔕 No alerts set")
        return

    symbols_to_delete = [symbol_complete(s.upper()) for s in args[1:]]
    logger.info(f"Looking for alerts with symbols: {symbols_to_delete}")
    
    matching_alerts = []
    for i, alert in enumerate(alerts, 1):
        if any(alert.get("symbol") == s for s in symbols_to_delete):
            matching_alerts.append((i, alert))

    if not matching_alerts:
        logger.info(f"No matching alerts found for symbols: {symbols_to_delete}")
        await event.reply(f"❌ No alerts found with symbols: {', '.join(symbols_to_delete)}")
        return

    logger.info(f"Found {len(matching_alerts)} matching alerts for deletion")
    message_parts = []
    for alert_id, alert in matching_alerts:
        symbol = alert.get("symbol")
        price = alert.get("price")
        message_parts.append(f"Alert #{alert_id}:\n• {symbol} - ${price:,.3f}")

    keyboard = [
        [
            Button.inline("Yes", f"delete_alert_yes_{','.join(str(a[0]) for a in matching_alerts)}"),
            Button.inline("No", "delete_alert_no"),
        ]
    ]
    
    await event.reply(
        f"❓ Are you sure you want to delete these alerts?\n\n" +
        "\n\n".join(message_parts),
        buttons=keyboard,
    )


@bot.on(events.CallbackQuery)
async def callback_handler(event):
    if event.data.startswith(b"delete_alert_yes_"):
        alert_ids = [int(id) for id in event.data.decode("utf-8").split("_")[-1].split(",")]
        logger.info(f"Deleting alerts with IDs: {alert_ids}")
        success = True
        for alert_id in alert_ids:
            if not await MonitorService.delete_monitor(db, event.chat_id, alert_id):
                logger.warning(f"Failed to delete alert {alert_id}")
                success = False
                break

        if success:
            logger.info(f"Successfully deleted alerts: {alert_ids}")
            await event.answer("✅ Alerts deleted successfully.")
        else:
            logger.error(f"Failed to delete some alerts: {alert_ids}")
            await event.answer("⚠️ Some alerts could not be deleted.")

    elif event.data == b"delete_alert_no":
        logger.info("Alert deletion canceled by user")
        await event.answer("❌ Deletion canceled.")

    elif event.data.startswith(b"delmon_yes_"):
        monitor_ids = [int(id) for id in event.data.decode("utf-8").split("_")[-1].split(",")]
        logger.info(f"Deleting monitors with IDs: {monitor_ids}")
        success = True
        for monitor_id in monitor_ids:
            if not await SignalService.delete_monitor(db, event.chat_id, monitor_id):
                logger.warning(f"Failed to delete monitor {monitor_id}")
                success = False
                break

        if success:
            logger.info(f"Successfully deleted monitors: {monitor_ids}")
            await event.answer("✅ Monitors deleted successfully.")
        else:
            logger.error(f"Failed to delete some monitors: {monitor_ids}")
            await event.answer("⚠️ Some monitors could not be deleted.")

    elif event.data == b"delmon_no":
        logger.info("Monitor deletion canceled by user")
        await event.answer("❌ Deletion canceled.")

    await event.delete()


@bot.on(events.NewMessage(pattern=r"^\/(?:p|price)"))
async def price_command(event):
    logger.info(f"Received /price command from chat_id: {event.chat_id}")
    try:
        args = event.message.text.split()
        if len(args) != 2:
            logger.warning(f"Invalid /price command format from chat_id: {event.chat_id}")
            await event.reply("⚠️ Please provide a symbol. Example: /price BTC/USDT\n")
            return

        symbol = symbol_complete(args[1].upper())
        logger.info(f"Fetching price for {symbol} for chat_id: {event.chat_id}")
        msg = await event.reply(f"📊 Fetching price data for {symbol}...")

        price_bot = CryptoPriceBot()
        ticker_data = await price_bot.fetch_latest_price(symbol)
        await price_bot.close()

        if not ticker_data:
            logger.warning(f"Unable to fetch price data for {symbol} for chat_id: {event.chat_id}")
            await msg.edit(f"❌ Unable to fetch data for {symbol}")
            return

        message = format_price_message(ticker_data)
        logger.info(f"Successfully fetched price for {symbol} for chat_id: {event.chat_id}")
        await msg.delete()
        await event.reply(message)
    except Exception as e:
        logger.error(f"Error in /price command for chat_id: {event.chat_id}: {str(e)}")
        await event.reply(f"❌ Error: {str(e)}")


@bot.on(events.NewMessage(pattern=r"^\/(?:f|filter)"))
async def filter_command(event, timeframe: str = "15m", threshold: float = 1.0):
    logger.info(f"Received /filter command from chat_id: {event.chat_id}")
    try:
        msg = await event.reply("📊 Fetching price data...")
        start_time = time.time()
        price_bot = CryptoPriceBot()
        _timeframe = timeframe
        _threshold = threshold

        args = event.message.text.split()
        if len(args) == 3:
            _timeframe = args[1]
            _threshold = float(args[2])
            logger.info(f"Using custom timeframe {_timeframe} and threshold {_threshold} for chat_id: {event.chat_id}")

        df = pd.read_csv("top_200_currencies.csv")
        symbols = df["symbol"].tolist()
        tasks = [
            price_bot.fetch_price_changes(symbol, _timeframe, threshold=_threshold)
            for symbol in symbols
        ]
        price_changes = await asyncio.gather(*tasks)
        await price_bot.close()

        if not price_changes:
            logger.warning(f"No price changes found for chat_id: {event.chat_id}")
            await event.reply("⚠️ Unable to fetch price data.")
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        message = f"🔄 Price Changes {_threshold}% in {_timeframe}\n📅 {timestamp}\n\n"
        for data in price_changes:
            if not data:
                continue
            emoji = "🟢" if data["pct_change"] >= 0 else "🔴"
            message += f"""{emoji} {data["symbol"]}: {data["pct_change"]:+.2f}%\n"""

        logger.info(f"Successfully generated filter results for chat_id: {event.chat_id}")
        await msg.delete()
        await event.reply(message)
        end_time = time.time()
        logger.info(f"Filter command completed in {end_time - start_time} seconds for chat_id: {event.chat_id}")
    except Exception as e:
        logger.error(f"Error in /filter command for chat_id: {event.chat_id}: {str(e)}")
        await event.reply(f"❌ Error: {str(e)}")


@bot.on(events.NewMessage(pattern=r"^\/(?:c|chart)" + PATTERN_TWO_ARGS))
async def chart_command(event):
    logger.info(f"Received /chart command from chat_id: {event.chat_id}")
    try:
        config = await get_config(event.chat_id)
        is_future_on = config.get("is_future", "off") == "on"
        args = event.message.text.split()
        if len(args) < 2:
            logger.warning(f"Invalid /chart command format from chat_id: {event.chat_id}")
            await event.reply(
                "⚠️ Please provide a symbol. Example: /chart BTC/USDT 4h\n"
                "Available timeframes: 1m, 5m, 15m, 1h, 4h, 1d\n"
            )
            return

        symbol = symbol_complete(args[1].upper())
        timeframe = args[2].lower() if len(args) > 2 else "1h"
        logger.info(f"Generating {timeframe} chart for {symbol} for chat_id: {event.chat_id}")

        msg = await event.reply(f"📊 Generating {timeframe} chart for {symbol}...")
        price_bot = CryptoPriceBot()

        df, exchange = await price_bot.fetch_ohlcv_data(symbol, timeframe, 200)
        if df is None:
            is_future_on = True
        if is_future_on:
            df_future, ft_exchange = await price_bot.fetch_future_ohlcv_data(
                symbol, timeframe, 200
            )
        await price_bot.close()

        if df is None or df.empty:
            logger.warning(f"Unable to fetch chart data for {symbol} for chat_id: {event.chat_id}")
            await msg.edit(f"❌ Unable to fetch data for {symbol}")
            return

        # Calculate some basic statistics
        change_pct = (
            (df["close"].iloc[-1] - df["close"].iloc[0]) / df["close"].iloc[0]
        ) * 100
        high = df["high"].max()
        low = df["low"].min()

        # Assuming df is your DataFrame and it has a DateTime index
        now = datetime.now()

        # Exclude the current hour
        df_excluding_current_hour = df[
            df.index < now.replace(minute=0, second=0, microsecond=0)
        ]

        # Get the last 24 rows excluding the current hour
        last_24_rows = df_excluding_current_hour.tail(24)
        volume_last_24h = last_24_rows["volume"].sum()

        # Get the previous 24 rows excluding the current hour
        previous_24_rows = df_excluding_current_hour.iloc[-48:-24]
        volume_previous_24h = previous_24_rows["volume"].sum()

        # volume change
        volume_change = (
            (volume_last_24h - volume_previous_24h) / volume_previous_24h * 100
        )

        # Create and send chart
        chart_buf = await price_bot.generate_chart(df, symbol, timeframe, exchange)
        if chart_buf is None:
            await msg.edit("❌ Error generating chart")
            return

        # Format caption
        caption = (
            f"📈 {symbol} {timeframe} Chart\n"
            f"Period: {df.iloc[0].name.strftime('%Y-%m-%d %H:%M')} - {df.iloc[-1].name.strftime('%Y-%m-%d %H:%M')}\n"
            f"Price: ${df['close'].iloc[-1]:,.4f}\n"
            f"Change {timeframe}: {change_pct:+.2f}% {'🟢' if change_pct >= 0 else '🔴'}\n"
            f"High: ${high:,.4f}\n"
            f"Low: ${low:,.4f}\n"
            f"Volume last 24h: ${volume_last_24h:,.2f}\n"
            f"Volume previous 24h: ${volume_previous_24h:,.2f}\t, change {'🟢' if volume_change >= 0 else '🔴'} {volume_change:,.2f}%\n"
        )

        logger.info(f"Successfully generated chart for {symbol} for chat_id: {event.chat_id}")
        await msg.delete()
        await bot.send_file(
            event.chat_id, chart_buf, caption=caption, force_document=False
        )

        # Chart future data
        if is_future_on and df_future is not None:
            chart_buf = await price_bot.generate_chart(
                df_future, symbol, timeframe, exchange
            )

            # Calculate some basic statistics
            change_pct = (
                (df_future["close"].iloc[-1] - df_future["close"].iloc[0])
                / df_future["close"].iloc[0]
            ) * 100
            high = df_future["high"].max()
            low = df_future["low"].min()

            # Assuming df is your DataFrame and it has a DateTime index
            now = datetime.now()

            # Exclude the current hour
            df_excluding_current_hour = df_future[
                df.index < now.replace(minute=0, second=0, microsecond=0)
            ]

            # Get the last 24 rows excluding the current hour
            last_24_rows = df_excluding_current_hour.tail(24)
            volume_last_24h = last_24_rows["volume"].sum()

            # Get the previous 24 rows excluding the current hour
            previous_24_rows = df_excluding_current_hour.iloc[-48:-24]
            volume_previous_24h = previous_24_rows["volume"].sum()

            # volume change
            volume_change = (
                (volume_last_24h - volume_previous_24h) / volume_previous_24h * 100
            )

            # Format caption
            caption = (
                f"📈 Future: {symbol} {timeframe} Chart\n"
                f"Period: {df_future.iloc[0].name.strftime('%Y-%m-%d %H:%M')} - {df_future.iloc[-1].name.strftime('%Y-%m-%d %H:%M')}\n"
                f"Price: ${df_future['close'].iloc[-1]:,.4f}\n"
                f"Change {timeframe}: {change_pct:+.2f}% {'🟢' if change_pct >= 0 else '🔴'}\n"
                f"High: ${high:,.4f}\n"
                f"Low: ${low:,.4f}\n"
                f"Volume last 24h: ${volume_last_24h:,.2f}\n"
                f"Volume previous 24h: ${volume_previous_24h:,.2f}\t, change {'🟢' if volume_change >= 0 else '🔴'} {volume_change:,.2f}%\n"
            )

            logger.info(f"Successfully generated future chart for {symbol} for chat_id: {event.chat_id}")
            await bot.send_file(
                event.chat_id,
                chart_buf,
                caption=caption,
                force_document=False,
                attributes=[DocumentAttributeFilename(chart_buf.name)],
            )

    except Exception as e:
        logger.error(f"Error in /chart command for chat_id: {event.chat_id}: {str(e)}")
        await event.reply(f"❌ Error: {str(e)}")


@bot.on(events.NewMessage(pattern=r"^\/(?!start\b|sentiment\b)(s|signal)"))
async def signal_command(event):
    logger.info(f"Received /signal command from chat_id: {event.chat_id}")
    try:
        args = event.message.text.split()
        if not (2 <= len(args) <= 3):
            logger.warning(f"Invalid /signal command format from chat_id: {event.chat_id}")
            await event.reply(
                "⚠️ Invalid command format.\n"
                "Usage: /signal <symbol> [timeframe]\n"
                "Example: /signal BTC 1h\n"
                "Available timeframes: 1m, 5m, 15m, 1h, 4h, 1d"
            )
            return

        symbol = symbol_complete(args[1].upper())
        timeframe = args[2].lower() if len(args) > 2 else "1h"
        
        valid_timeframes = ["1m", "5m", "15m", "1h", "4h", "1d"]
        if timeframe not in valid_timeframes:
            logger.warning(f"Invalid timeframe {timeframe} for chat_id: {event.chat_id}")
            await event.reply(
                "⚠️ Invalid timeframe.\n"
                f"Available timeframes: {', '.join(valid_timeframes)}"
            )
            return

        logger.info(f"Analyzing signals for {symbol} ({timeframe}) for chat_id: {event.chat_id}")
        msg = await event.reply(f"🔎 Analyzing signals for {symbol} ({timeframe})...")

        price_bot = CryptoPriceBot()
        try:
            df, exchange = await price_bot.fetch_ohlcv_data(symbol, timeframe)
        finally:
            await price_bot.close()

        if df is None or df.empty:
            logger.warning(f"Unable to fetch market data for {symbol} for chat_id: {event.chat_id}")
            await msg.edit(f"❌ Unable to fetch market data for {symbol}")
            return

        current_price = df['close'].iloc[-1]
        price_change = ((current_price - df['close'].iloc[0]) / df['close'].iloc[0]) * 100
        signals = await quant_agent(df)

        logger.info(f"Successfully generated signals for {symbol} for chat_id: {event.chat_id}")
        response = (
            f"📈 Trading Signals for {symbol} ({timeframe})\n\n"
            f"Current Price: ${current_price:,.4f}\n"
            f"Price Change: {price_change:+.2f}% {'🟢' if price_change >= 0 else '🔴'}\n"
            f"Exchange: {exchange}\n\n"
            f"Analysis:\n{signals}"
        )
        await msg.edit(response, parse_mode="html")
    except ValueError as e:
        logger.error(f"ValueError in /signal command for chat_id: {event.chat_id}: {str(e)}")
        await event.reply(f"❌ Invalid input: {str(e)}")
    except Exception as e:
        logger.error(f"Error in /signal command for chat_id: {event.chat_id}: {str(e)}")
        await event.reply(f"❌ An unexpected error occurred: {str(e)}")


@bot.on(events.NewMessage(pattern=r"^\/calendar"))
async def get_all_economic_calendar(event):
    logger.info(f"Received /calendar command from chat_id: {event.chat_id}")
    try:
        loc = final_table()
        if not isinstance(loc, str):
            logger.info(f"Sending economic calendar data to chat_id: {event.chat_id}")
            for i, row in loc.iterrows():
                message = (
                    f"{row['Time']} {row['Flag']} {row['Imp']} | "
                    f"{row['Event']}\n"
                    f"Actual: {row['Actual']} | Forecast: {row['Forecast']} | Previous: {row['Previous']}"
                )
                await bot.send_message(event.chat_id, message)
            logger.info(f"Successfully sent economic calendar data to chat_id: {event.chat_id}")
    except Exception as e:
        logger.error(f"Error in /calendar command for chat_id: {event.chat_id}: {str(e)}")
        await event.reply(f"❌ Error: {str(e)}")


@bot.on(events.NewMessage(pattern=r"^\/(?:mon|monitor)"))
async def add_monitor_symbol(event):
    args = event.message.text.split()
    if len(args) == 1:
        logger.info(f"Fetching monitors for chat_id: {event.chat_id}")
        query = await db.signals.find_one({"chat_id": event.chat_id})
        if not query:
            logger.info(f"No monitors found for chat_id: {event.chat_id}")
            await event.reply("🔕 No signals set")
            return

        signals = query.get("data", [])
        logger.info(f"Found {len(signals)} monitors for chat_id: {event.chat_id}")
        list_signals = "\n".join(
            [f"{i + 1}. {signals[i]}" for i in range(len(signals))]
        )
        await event.reply(f"🔔 Signals: \n{list_signals}")
        return

    chat_id = event.chat_id
    symbols = [symbol_complete(args[i].upper()) for i in range(1, len(args))]
    logger.info(f"Adding new monitor for symbols: {symbols}")
    added_id = await SignalService.add_monitor(db, chat_id, symbols, 0)
    logger.info(f"Successfully added monitor {added_id} for symbols: {symbols}")
    await event.reply(f"✅ Monitor {added_id} set for {symbols}")


@bot.on(events.NewMessage(pattern=r"^\/(?:delmon|delete_monitor)"))
async def delete_monitor_symbol(event):
    args = event.message.text.split()
    if len(args) < 2:
        logger.warning("Delete monitor command called without symbols")
        await event.reply(
            "⚠️ Please provide at least one symbol to delete.\n"
            "Usage: /delmon <symbol1> [symbol2] [symbol3] ...\n"
            "Example: /delmon ETH XRP WLD"
        )
        return

    chat_id = event.chat_id
    logger.info(f"Fetching monitors for deletion for chat_id: {chat_id}")
    query = await db.signals.find_one({"chat_id": chat_id})
    signals = query.get("data", [])

    if not signals:
        logger.info(f"No monitors found for chat_id: {chat_id}")
        await event.reply("🔕 No monitors set")
        return

    symbols_to_delete = [symbol_complete(s.upper()) for s in args[1:]]
    logger.info(f"Looking for monitors with symbols: {symbols_to_delete}")
    
    matching_monitors = []
    for i, symbol in enumerate(signals, 1):
        if any(symbol == s for s in symbols_to_delete):
            matching_monitors.append((i, symbol))

    if not matching_monitors:
        logger.info(f"No matching monitors found for symbols: {symbols_to_delete}")
        await event.reply(f"❌ No monitors found with symbols: {', '.join(symbols_to_delete)}")
        return

    logger.info(f"Found {len(matching_monitors)} matching monitors for deletion")
    message_parts = []
    for monitor_id, symbol in matching_monitors:
        message_parts.append(f"Monitor #{monitor_id}:\n• {symbol}")

    keyboard = [
        [
            Button.inline("Yes", f"delmon_yes_{','.join(str(m[0]) for m in matching_monitors)}"),
            Button.inline("No", "delmon_no"),
        ]
    ]
    
    await event.reply(
        f"❓ Are you sure you want to delete these monitors?\n\n" +
        "\n\n".join(message_parts),
        buttons=keyboard,
    )

@bot.on(events.NewMessage(pattern=r"^\/llm"))
async def llm_command(event):
    logger.info(f"Received /llm command from chat_id: {event.chat_id}")
    try:
        args = event.message.text.split(maxsplit=1)
        if len(args) < 2:
            logger.warning(f"Invalid /llm command format from chat_id: {event.chat_id}")
            await event.reply(
                "⚠️ Please provide a prompt.\n"
                "Usage: /llm <your prompt>\n"
                "Example: /llm What's the current price of Bitcoin?"
            )
            return

        prompt = args[1]
        logger.info(f"Processing LLM request for chat_id: {event.chat_id}, prompt: {prompt}")
        msg = await event.reply("🤔 Processing your request...")
        
        process = await asyncio.create_subprocess_exec(
            'llm', prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error occurred"
            logger.error(f"LLM process error for chat_id: {event.chat_id}: {error_msg}")
            await msg.edit(f"❌ Error processing request: {error_msg}")
            return
            
        output = stdout.decode().strip()
        if not output:
            logger.warning(f"Empty LLM response for chat_id: {event.chat_id}")
            await msg.edit("❌ No response received")
            return
            
        logger.info(f"Successfully processed LLM request for chat_id: {event.chat_id}")
        await msg.edit(f"🤖 Response:\n\n{output}")
        
    except Exception as e:
        logger.error(f"Error in /llm command for chat_id: {event.chat_id}: {str(e)}")
        await event.reply(f"❌ Error: {str(e)}")
