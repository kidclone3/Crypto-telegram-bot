import asyncio
import copy
from datetime import datetime
import json
import time
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
from src.services.sentiment_service import get_latest_sentiment
from src.utils import format_price_message, symbol_complete
from src.core.db import motor_client

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
    "/sentiment - Get latest market sentiment data\n\n"
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
    # add a run loop to monitor price

    # Check the config for the chat
    chat_id = event.chat_id

    config = await db.config.find_one({"chat_id": chat_id})

    if not config:
        await db.config.insert_one({"chat_id": chat_id, **DEFAULT_CONFIG})

    await event.reply(START_MSG)


@bot.on(events.NewMessage(pattern=r"^\/help$"))
async def send_help(event):
    await event.reply(START_MSG)


@bot.on(events.NewMessage(pattern=r"^\/ping$"))
async def echo_all(event):
    await event.reply("pong")


@bot.on(events.NewMessage(pattern=r"^\/config"))
async def config_command(event):
    args = event.message.text.split()
    # Get the chat_id
    chat_id = event.chat_id

    # get the config for the chat
    config = await get_config(chat_id)

    if len(args) == 1:
        if not config:
            await event.reply("⚠️ No configuration found.")
            return
        else:
            print_config = copy.deepcopy(config)
            del print_config["_id"]
            del print_config["chat_id"]

            await event.reply(
                f"🔧 Configuration for you:\n"
                f"{json.dumps(print_config, indent=4, default=str)}"
            )
    elif len(args) == 3:
        # Set the configuration

        config_key = args[1]
        config_value = args[2]

        if config_key not in config.keys():
            await event.reply("⚠️ Invalid configuration key.")
            return

        def validate_on_off(value: str):
            return value.lower() not in ["on", "off"]

        if config_key == "is_alert":
            if validate_on_off(config_value.lower()):
                await event.reply("⚠️ Invalid value for is_alert. Use 'on' or 'off'.")
                return
            config_value = config_value.lower()
        elif config_key == "is_future":
            if validate_on_off(config_value.lower()):
                await event.reply("⚠️ Invalid value for is_future. Use 'on' or 'off'.")
                return
            config_value = config_value.lower()
        elif config_key == "price_threshold":
            config_value = float(config_value)
        elif config_key == "alert_interval":
            config_value = int(config_value)

        db.config.update_one(
            {"chat_id": chat_id},
            {"$set": {config_key: config_value}},
        )
        await event.reply(f"✅ Configuration updated: {config_key} = {config_value}")


@bot.on(events.NewMessage(pattern=r"^\/(?:a|alert)"))
async def add_alert(event):
    args = event.message.message.split(" ")
    chat_id = event.chat_id
    if len(args) == 1:
        query = await db.alerts.find_one({"chat_id": chat_id})
        alerts = []
        if query:
            alerts = query.get("data", [])

        if not alerts:
            await event.reply("🔕 No alerts set")
            return

        table_header = ["ID", "Symbol", "Price ($)", "Message"]
        table_body = []
        # Add numbers to the alerts
        for i, alert in enumerate(alerts):
            symbol, price, msg = (
                alert.get("symbol"),
                alert.get("price"),
                alert.get("msg", ""),
            )
            table_body.append([i + 1, symbol, f"${price}", msg])

        # Convert table to string
        alert_table = tabulate(table_body, headers=table_header, tablefmt="pretty")

        await event.reply(f"🔔 Alerts:\n<pre>{alert_table}</pre>", parse_mode="HTML")
        return
    else:
        price = float(args[2])
        msg = " ".join(args[3:]) if len(args) > 3 else None
        if args[1].isnumeric():
            # Update alert by index
            alert_id = int(args[1])
            data = {"id": alert_id, "price": price, "msg": msg}
            symbol = await MonitorService.update_monitor(db, chat_id, data)
            if not symbol:
                await event.reply("⚠️ Invalid alert ID")
                return
            # Send confirmation message
            await event.reply(
                f"✅ Alert ID {alert_id} of symbol {symbol} updated to ${price:,.3f}\n Message: {msg}"
            )

            return
        symbol = symbol_complete(args[1].upper())
        data = {
            "symbol": symbol,
            "price": price,
            "msg": msg,
        }
        added_id = await MonitorService.add_monitor(db, chat_id, data)
        # Send confirmation message
        await event.reply(
            f"✅ Alert {added_id} set for {symbol} at ${price:,.3f}\n Message: {msg}"
        )


@bot.on(events.NewMessage(pattern=r"^\/(?:dela|delete_alert)"))
async def delete_alert(event):
    args = event.message.text.split()
    if len(args) != 2:
        await event.reply("⚠️ Please provide an alert ID to delete")
        return

    try:
        alert_id = int(args[1])
    except ValueError:
        await event.reply("⚠️ Invalid alert ID")
        return
    chat_id = event.chat_id
    query = await db.alerts.find_one({"chat_id": chat_id})
    alerts = query.get("data", [])

    if not alerts:
        await event.reply("🔕 No alerts set")
        return

    if alert_id < 1 or alert_id > len(alerts):
        await event.reply("⚠️ Invalid alert ID")
        return

    # Show confirmation message with buttons
    keyboard = [
        [
            Button.inline("Yes", f"delete_alert_yes_{alert_id}"),
            Button.inline("No", "delete_alert_no"),
        ]
    ]
    symbol = alerts[alert_id - 1].get("symbol")
    price = alerts[alert_id - 1].get("price")
    await event.reply(
        f"❓ Are you sure you want to delete alert ID {alert_id}: {symbol} - {price}?",
        buttons=keyboard,
    )


@bot.on(events.CallbackQuery)
async def callback_handler(event):
    # Check if the callback data starts with 'delete_alert_yes_'
    if event.data.startswith(b"delete_alert_yes_"):
        delete_id = int(event.data.decode("utf-8").split("_")[-1])
        if not await MonitorService.delete_monitor(db, event.chat_id, delete_id):
            await event.answer("⚠️ Alert ID not found.")
            return

        await event.answer("✅ Alert deleted successfully.")

    elif event.data == b"delete_alert_no":
        await event.answer("❌ Deletion canceled.")

    elif event.data.startswith(b"delmon_yes_"):
        delete_id = int(event.data.decode("utf-8").split("_")[-1])
        if not await SignalService.delete_monitor(db, event.chat_id, delete_id):
            await event.answer("⚠️ Monitor ID not found.")
            return

        await event.answer("✅ Monitor deleted successfully.")

    elif event.data == b"delmon_no":
        await event.answer("❌ Deletion canceled.")

    await event.delete()


@bot.on(events.NewMessage(pattern=r"^\/(?:p|price)"))
async def price_command(event):
    try:
        # Check if symbol is provided
        args = event.message.text.split()
        if len(args) != 2:
            await event.reply("⚠️ Please provide a symbol. Example: /price BTC/USDT\n")
            return

        # Get the symbol and ensure it's uppercase
        symbol = symbol_complete(args[1].upper())

        msg = await event.reply(f"📊 Fetching price data for {symbol}...")

        # Create a new bot instance for this request
        price_bot = CryptoPriceBot()
        ticker_data = await price_bot.fetch_latest_price(symbol)
        await price_bot.close()

        if not ticker_data:
            await msg.edit(f"❌ Unable to fetch data for {symbol}")
            return

        # Format the message
        # TODO: The data to message is not correct: Impossible to get the 24h change from the ticker data
        message = format_price_message(ticker_data)
        # delete the latest bot message and send the new message
        await msg.delete()
        await event.reply(message)
    except Exception as e:
        await event.reply(f"❌ Error: {str(e)}")


@bot.on(events.NewMessage(pattern=r"^\/(?:f|filter)"))
async def filter_command(event, timeframe: str = "15m", threshold: float = 1.0):
    msg = await event.reply("📊 Fetching price data...")
    try:
        start_time = time.time()
        price_bot = CryptoPriceBot()
        _timeframe = timeframe
        _threshold = threshold

        args = event.message.text.split()
        if len(args) == 3:
            _timeframe = args[1]
            _threshold = float(args[2])
        df = pd.read_csv("top_200_currencies.csv")
        symbols = df["symbol"].tolist()
        tasks = [
            price_bot.fetch_price_changes(symbol, _timeframe, threshold=_threshold)
            for symbol in symbols
        ]
        price_changes = await asyncio.gather(*tasks)
        await price_bot.close()

        if not price_changes:
            await event.reply("⚠️ Unable to fetch price data.")
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        message = f"🔄 Price Changes {_threshold}% in {_timeframe}\n📅 {timestamp}\n\n"
        for data in price_changes:
            if not data:
                continue
            emoji = "🟢" if data["pct_change"] >= 0 else "🔴"
            message += f"""{emoji} {data["symbol"]}: {data["pct_change"]:+.2f}%\n"""

        await msg.delete()
        await event.reply(message)
        end_time = time.time()
        print(f"Time taken: {end_time - start_time}")

    except Exception as e:
        await event.reply(f"❌ Error: {str(e)}")


@bot.on(events.NewMessage(pattern=r"^\/(?:c|chart)" + PATTERN_TWO_ARGS))
async def chart_command(event):
    try:
        config = await get_config(event.chat_id)
        is_future_on = config.get("is_future", "off") == "on"
        args = event.message.text.split()
        if len(args) < 2:
            await event.reply(
                "⚠️ Please provide a symbol. Example: /chart BTC/USDT 4h\n"
                "Available timeframes: 1m, 5m, 15m, 1h, 4h, 1d\n"
            )
            return

        # Parse arguments
        symbol = symbol_complete(args[1].upper())
        timeframe = args[2].lower() if len(args) > 2 else "1h"

        # Send loading message
        msg = await event.reply(f"📊 Generating {timeframe} chart for {symbol}...")

        # Get candle data and create chart
        price_bot = CryptoPriceBot()

        df, exchange = await price_bot.fetch_ohlcv_data(symbol, timeframe, 200)
        if df is None:  # If no data is returned, try fetching future data
            is_future_on = True
        if is_future_on:
            df_future, ft_exchange = await price_bot.fetch_future_ohlcv_data(
                symbol, timeframe, 200
            )
        await price_bot.close()

        if df is None or df.empty:
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

        # Delete loading message and send chart
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

            # await event.reply(file=chart_buf)
            await bot.send_file(
                event.chat_id,
                chart_buf,
                caption=caption,
                force_document=False,
                attributes=[DocumentAttributeFilename(chart_buf.name)],
            )

    except Exception as e:
        await event.reply(f"❌ Error: {str(e)}")


@bot.on(events.NewMessage(pattern=r"^\/(?!start\b|sentiment\b)(s|signal)"))
async def signal_command(event):
    try:
        args = event.message.text.split(" ")
        if len(args) < 2 or len(args) > 3:
            await event.reply("⚠️ Please provide a symbol. Example: /signal btc\n")
            return
        # Parse arguments
        symbol = symbol_complete(args[1].upper())
        timeframe = args[2].lower() if len(args) > 2 else "1h"

        # Send loading message
        msg = await event.reply(f"🔎 Finding signal for {symbol}...")

        # Get candle data and create chart
        price_bot = CryptoPriceBot()
        df, _ = await price_bot.fetch_ohlcv_data(symbol, timeframe)
        await price_bot.close()

        if df is None or df.empty:
            await msg.edit(f"❌ Unable to fetch data for {symbol}")
            return

        # Call indicators.py to get signals
        signals = await quant_agent(df)

        # Delete loading message and send chart
        await msg.delete()
        await event.reply(
            f"📈 Signals for {symbol} ({timeframe}):\n"
            f"Current Price: ${df['close'].iloc[-1]:,.4f}\n"
            f"\n\n{signals}",
            parse_mode="html",
        )

    except Exception as e:
        await event.reply(f"❌ Error: {str(e)}")


@bot.on(events.NewMessage(pattern=r"^\/calendar"))
async def get_all_economic_calendar(event):
    loc = final_table()
    if not isinstance(loc, str):
        try:
            for i, row in loc.iterrows():
                message = (
                    f"{row['Time']} {row['Flag']} {row['Imp']} | "
                    f"{row['Event']}\n"
                    f"Actual: {row['Actual']} | Forecast: {row['Forecast']} | Previous: {row['Previous']}"
                )
                await bot.send_message(event.chat_id, message)
        except Exception as e:
            await event.reply(f"❌ Error: {str(e)}")


@bot.on(events.NewMessage(pattern=r"^\/(?:mon|monitor)"))
async def add_monitor_symbol(event):
    args = event.message.text.split()
    if len(args) == 1:
        # show list signals
        query = await db.signals.find_one({"chat_id": event.chat_id})
        if not query:
            await event.reply("🔕 No signals set")
            return

        signals = query.get("data", [])
        # list signals
        list_signals = "\n".join(
            [f"{i + 1}. {signals[i]}" for i in range(len(signals))]
        )
        await event.reply(f"🔔 Signals: \n{list_signals}")
        return

    chat_id = event.chat_id
    symbols = [symbol_complete(args[i].upper()) for i in range(1, len(args))]

    added_id = await SignalService.add_monitor(db, chat_id, symbols, 0)
    # Send confirmation message
    await event.reply(f"✅ Monitor {added_id} set for {symbols}")


@bot.on(events.NewMessage(pattern=r"^\/(?:delmon|delete_monitor)"))
async def delete_monitor_symbol(event):
    args = event.message.text.split()
    if len(args) != 2:
        await event.reply("⚠️ Please provide a monitor ID to delete")
        return

    try:
        monitor_id = int(args[1])
    except ValueError:
        await event.reply("⚠️ Invalid monitor ID")
        return
    chat_id = event.chat_id
    query = await db.signals.find_one({"chat_id": chat_id})
    signals = query.get("data", [])

    if not signals:
        await event.reply("🔕 No signals set")
        return

    if monitor_id < 1 or monitor_id > len(signals):
        await event.reply("⚠️ Invalid monitor ID")
        return

    # Show confirmation message with buttons
    keyboard = [
        [
            Button.inline("Yes", f"delmon_yes_{monitor_id}"),
            Button.inline("No", "delmon_no"),
        ]
    ]
    await event.reply(
        f"❓ Are you sure you want to delete monitor ID {monitor_id}?",
        buttons=keyboard,
    )


@bot.on(events.NewMessage(pattern=r"^\/sentiment$"))
async def get_sentiment(event):
    sentiment_str = get_latest_sentiment()
    await event.reply(f"📊 Latest sentiment data:\n{sentiment_str}")
