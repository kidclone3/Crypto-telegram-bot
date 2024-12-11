import asyncio
from datetime import datetime
import time
import aiofiles
from tabulate import tabulate
from telethon import Button, TelegramClient, events
from telethon.types import DocumentAttributeFilename
import pandas as pd

from src.services.price_bot import CryptoPriceBot
from src.core.config import settings
from src.utils import format_price_message, symbol_complete


START_MSG = (
    "👋 Welcome to the Crypto Price Bot!\n\n"
    "Available commands:\n"
    "/a or /alert - Add a cryptocurrency to the monitored list\n"
    "\t E.g: /a BTC 1000000 - Set alert on BTC at 100k\n"
    "/p or /prices - Get current price\n"
    "\t E.g: /p BTC\n"
    "/filter - Filter price changes by timeframe and percentage\n"
    "\t E.g: /f 15m 1 \n"
    "/c or /chart - Get price chart for a cryptocurrency\n"
    "/h or /help - Show this help message\n"
    "/ping - Check if the bot is online"
)

bot: TelegramClient = TelegramClient("bot", settings.api_id, settings.api_hash).start(
    bot_token=settings.bot_token
)


@bot.on(events.NewMessage(pattern="/start"))
async def send_welcome(event):
    await event.reply(START_MSG)


# @bot.on(events.NewMessage(pattern=QUERY_PATTERN))
# async def parse_request(event):
#     try:
#         result = await parser.parse_by_query(event.text)
#     except NotImplementedError as e:
#         result = e.args[0]
#     await event.reply(result)


@bot.on(events.NewMessage(pattern="/ping"))
async def echo_all(event):
    await event.reply("pong")


@bot.on(events.NewMessage(pattern="/(a|alert)"))
async def add_alert(event):
    args = event.message.message.split(" ")
    if len(args) not in [1, 3]:
        await event.reply("Invalid alert format")

    if len(args) == 1:
        # Print the list of alerts
        async with aiofiles.open("alert_list.txt", "r") as f:
            alerts = await f.readlines()
        if not alerts:
            await event.reply("🔕 No alerts set")
            return

        table_header = ["ID", "Symbol", "Price ($)"]
        table_body = []
        # Add numbers to the alerts
        for i, alert in enumerate(alerts):
            symbol, price = alert.split(",")
            table_body.append([i + 1, symbol, f"${price}"])

        # Convert table to string
        alert_table = tabulate(table_body, headers=table_header, tablefmt="pretty")

        await event.reply(f"🔔 Alerts:\n<pre>{alert_table}</pre>", parse_mode="HTML")
        return
    else:
        price = float(args[2])
        if args[1].isnumeric():
            # Update alert by index
            alert_id = int(args[1].isnumeric())
            async with aiofiles.open("alert_list.txt", "r") as f:
                alerts = await f.readlines()

            if not alerts:
                await event.reply("🔕 No alerts set")
                return

            if alert_id < 1 or alert_id > len(alerts):
                await event.reply("⚠️ Invalid alert ID")
                return
            symbol = alerts[alert_id - 1].split(",")[0]
            alerts[alert_id - 1] = f"{symbol},{price}\n"

            async with aiofiles.open("alert_list.txt", "w") as f:
                await f.writelines(alerts)

            # Send confirmation message
            await event.reply(
                f"✅ Alert ID {alert_id} of symbol {symbol} updated to ${price:,.3f}"
            )

            return
        symbol = symbol_complete(args[1].upper())

        async with aiofiles.open("alert_list.txt", "a") as f:
            await f.write(f"{symbol},{price}\n")

        # Send confirmation message
        await event.reply(f"✅ Alert 1 set for {symbol} at ${price:,.3f}")

    await event.reply("Adding alert")


@bot.on(events.NewMessage(pattern="/d|/delete"))
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

    async with aiofiles.open("alert_list.txt", "r") as f:
        alerts = await f.readlines()

    if not alerts:
        await event.reply("🔕 No alerts set")
        return

    if alert_id < 1 or alert_id > len(alerts):
        await event.reply("⚠️ Invalid alert ID")
        return

    # Show confirmation message with buttons
    keyboard = [
        [
            Button.inline("Yes", f"delete_yes_{alert_id}"),
            Button.inline("No", "delete_no"),
        ]
    ]

    await event.reply(
        f"❓ Are you sure you want to delete alert ID {alert_id}?",
        buttons=keyboard,
    )


@bot.on(events.CallbackQuery)
async def callback_handler(event):
    # Check if the callback data starts with 'delete_yes_'
    if event.data.startswith(b"delete_yes_"):
        alert_id = int(event.data.decode("utf-8").split("_")[-1])

        # Here, you would handle the deletion logic
        async with aiofiles.open("alert_list.txt", "r") as f:
            alerts = await f.readlines()

        if len(alerts) < alert_id:
            await event.answer("⚠️ Alert ID not found.")
            return

        # Remove the alert from the list
        del alerts[alert_id - 1]  # Adjust for zero-based index

        async with aiofiles.open("alert_list.txt", "w") as f:
            await f.writelines(alerts)

        await event.answer("✅ Alert deleted successfully.")

    elif event.data == b"delete_no":
        await event.answer("❌ Deletion canceled.")


@bot.on(events.NewMessage(pattern="/p|/price"))
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
        message = format_price_message(ticker_data)
        # delete the latest bot message and send the new message
        await msg.delete()
        await event.reply(message)
    except Exception as e:
        await event.reply(f"❌ Error: {str(e)}")


@bot.on(events.NewMessage(pattern="/f|/filter"))
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


@bot.on(events.NewMessage(pattern="/c|/chart"))
async def chart_command(event):
    try:
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

        # Validate timeframe
        valid_timeframes = ["1m", "5m", "15m", "1h", "4h", "1d"]
        if timeframe not in valid_timeframes:
            await event.reply(
                f"⚠️ Invalid timeframe. Please choose from: {', '.join(valid_timeframes)}"
            )
            return

        # Send loading message
        msg = await event.reply(f"📊 Generating {timeframe} chart for {symbol}...")

        # Get candle data and create chart
        price_bot = CryptoPriceBot()
        df = await price_bot.fetch_ohlcv_data(symbol, timeframe)
        df_future = await price_bot.fetch_future_ohlcv_data(symbol, timeframe)
        await price_bot.close()

        if df is None or df.empty:
            await msg.edit(f"❌ Unable to fetch data for {symbol}")
            return

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

        # Create and send chart
        chart_buf = await price_bot.generate_chart(df, symbol, timeframe)
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
        if df_future is not None:
            chart_buf = await price_bot.generate_chart(df_future, symbol, timeframe)

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