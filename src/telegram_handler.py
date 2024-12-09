from typing import List
import aiofiles
from datetime import datetime
import time
from tabulate import tabulate
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
import asyncio
from utils import symbol_complete, format_price_message
from crypto_price_bot import CryptoPriceBot


class TelegramHandler:
    def __init__(self, token: str, symbols: List[str]):
        self.application = Application.builder().token(token).build()
        self.symbols = symbols
        self.timeframe = "15m"
        self.threshold = 1.0

        # Alert settings
        self.alert_check_interval = 60  # Check alerts every 60 seconds
        self.price_threshold = 0.005  # 0.5% threshold for price alerts

        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler(["a", "alert"], self.alert_command))
        self.application.add_handler(
            CommandHandler(["d", "delete"], self.delete_alert_command)
        )
        self.application.add_handler(CommandHandler(["p", "price"], self.price_command))
        self.application.add_handler(
            CommandHandler(["f", "filter"], self.filter_command)
        )
        self.application.add_handler(CommandHandler(["c", "chart"], self.chart_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("ping", self.ping_command))
        self.application.add_handler(CallbackQueryHandler(self.button_callback))

    async def ping_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🏓 Pong!")

    async def start_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        welcome_msg = (
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
        await update.message.reply_text(welcome_msg)

        context.job_queue.run_repeating(
            self.monitor_alerts,
            interval=self.alert_check_interval,
            chat_id=update.message.chat_id,
        )
        print("all jobs: ", context.job_queue.jobs())

    async def help_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        help_msg = (
            "🤖 Crypto Price Bot Commands:\n\n"
            "/p or /prices - Get 1h price changes for monitored cryptocurrencies\n"
            "/a or /alert BTC 1000000 - Add an alert for BTC at 100k\n"
            "/a or /alert 1 100 - Update alert for index at $100\n"
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

            msg = await update.message.reply_text(
                f"📊 Fetching price data for {symbol}..."
            )

            # Create a new bot instance for this request
            price_bot = CryptoPriceBot()
            ticker_data = await price_bot.fetch_latest_price(symbol)
            await price_bot.close()

            if not ticker_data:
                await msg.edit_text(f"❌ Unable to fetch data for {symbol}")
                return

            # Format the message
            message = format_price_message(ticker_data)
            # delete the latest bot message and send the new message
            await msg.delete()
            await update.message.reply_text(message)
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def filter_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        msg = await update.message.reply_text("📊 Fetching price data...")
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
            message = (
                f"🔄 Price Changes {_threshold}% in {_timeframe}\n📅 {timestamp}\n\n"
            )
            for data in price_changes:
                if not data:
                    continue
                emoji = "🟢" if data["pct_change"] >= 0 else "🔴"
                message += f"""{emoji} {data["symbol"]}: {data["pct_change"]:+.2f}%\n"""

            await msg.delete()
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

            # Send loading message
            msg = await update.message.reply_text(
                f"📊 Generating {timeframe} chart for {symbol}..."
            )

            # Get candle data and create chart
            price_bot = CryptoPriceBot()
            df = await price_bot.fetch_ohlcv_data(symbol, timeframe)
            df_future = await price_bot.fetch_future_ohlcv_data(symbol, timeframe)
            await price_bot.close()

            if df is None or df.empty:
                await msg.edit_text(f"❌ Unable to fetch data for {symbol}")
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
            chart_buf = await price_bot.generate_chart(df, symbol, timeframe)
            if chart_buf is None:
                await msg.edit_text("❌ Error generating chart")
                return

            # Format caption
            caption = (
                f"📈 {symbol} {timeframe} Chart\n"
                f"Period: {df.iloc[0].name.strftime('%Y-%m-%d %H:%M')} - {df.iloc[-1].name.strftime('%Y-%m-%d %H:%M')}\n"
                f"Price: ${df['close'].iloc[-1]:,.4f}\n"
                f"Change: {change_pct:+.2f}% {'🟢' if change_pct >= 0 else '🔴'}\n"
                f"High: ${high:,.4f}\n"
                f"Low: ${low:,.4f}\n"
                f"Volume last 24h: ${volume_last_24h:,.2f}\n"
                f"Volume previous 24h: ${volume_previous_24h:,.2f}\t, change {'🟢' if volume_change >= 0 else '🔴'} {volume_change:,.2f}%\n"
            )

            # Delete loading message and send chart
            await msg.delete()
            await update.message.reply_photo(chart_buf, caption=caption)

            # Chart future data
            if df_future is not None:
                chart_buf = await price_bot.generate_chart(df_future, symbol, timeframe)

                # Format caption
                caption = (
                    f"📈 Future: {symbol} {timeframe} Chart\n"
                    f"Period: {df_future.iloc[0].name.strftime('%Y-%m-%d %H:%M')} - {df_future.iloc[-1].name.strftime('%Y-%m-%d %H:%M')}\n"
                    f"Price: ${df_future['close'].iloc[-1]:,.4f}\n"
                    f"Change: {change_pct:+.2f}% {'🟢' if change_pct >= 0 else '🔴'}\n"
                    f"High: ${high:,.4f}\n"
                    f"Low: ${low:,.4f}\n"
                    f"Volume last 24h: ${volume_last_24h:,.2f}\n"
                    f"Volume previous 24h: ${volume_previous_24h:,.2f}\t, change {'🟢' if volume_change >= 0 else '🔴'} {volume_change:,.2f}%\n"
                )

                await update.message.reply_photo(chart_buf, caption=caption)

        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def alert_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle the /add command
        Usage: /add or  /add <symbol> <price>
        Example: /add BTC/USDT 10000
        """
        if not context.args:
            # Print the list of alerts
            async with aiofiles.open("alert_list.txt", "r") as f:
                alerts = await f.readlines()
            if not alerts:
                await update.message.reply_text("🔕 No alerts set")
                return

            # alert_table = pt.PrettyTable(["ID", "Symbol", "Price ($)"])
            # alert_table.align["Symbol"] = "l"

            table_header = ["ID", "Symbol", "Price ($)"]
            table_body = []
            # Add numbers to the alerts
            for i, alert in enumerate(alerts):
                symbol, price = alert.split(",")
                table_body.append([i + 1, symbol, f"${price}"])

            # Convert table to string
            alert_table = tabulate(table_body, headers=table_header, tablefmt="pretty")

            await update.message.reply_text(
                f"🔔 Alerts:\n<pre>{alert_table}</pre>", parse_mode="HTML"
            )
            return

        # Read the arguments
        if len(context.args) != 2:
            await update.message.reply_text(
                "⚠️ Please provide a symbol and price. Example: /add BTC/USDT 10000"
            )
            return

        price = float(context.args[1])

        if context.args[0].isnumeric():
            # Update alert by index
            alert_id = int(context.args[0])
            async with aiofiles.open("alert_list.txt", "r") as f:
                alerts = await f.readlines()

            if not alerts:
                await update.message.reply_text("🔕 No alerts set")
                return

            if alert_id < 1 or alert_id > len(alerts):
                await update.message.reply_text("⚠️ Invalid alert ID")
                return
            symbol = alerts[alert_id - 1].split(",")[0]
            alerts[alert_id - 1] = f"{symbol},{price}\n"

            async with aiofiles.open("alert_list.txt", "w") as f:
                await f.writelines(alerts)

            # Send confirmation message
            await update.message.reply_text(
                f"✅ Alert ID {alert_id} of symbol {symbol} updated to ${price:,.3f}"
            )

            return

        symbol = symbol_complete(context.args[0].upper())

        async with aiofiles.open("alert_list.txt", "a") as f:
            await f.write(f"{symbol},{price}\n")

        # Send confirmation message
        await update.message.reply_text(f"✅ Alert set for {symbol} at ${price:,.3f}")
        pass

    async def delete_alert_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle the /delete command
        Usage: /delete <id>
        Example: /delete 1
        """
        if not context.args or len(context.args) != 1:
            await update.message.reply_text("⚠️ Please provide an alert ID to delete")
            return

        alert_id = int(context.args[0])

        async with aiofiles.open("alert_list.txt", "r") as f:
            alerts = await f.readlines()

        if not alerts:
            await update.message.reply_text("🔕 No alerts set")
            return

        if alert_id < 1 or alert_id > len(alerts):
            await update.message.reply_text("⚠️ Invalid alert ID")
            return
        # Show confirmation message with buttons
        keyboard = [
            [
                InlineKeyboardButton("Yes", callback_data=f"delete_yes_{alert_id}"),
                InlineKeyboardButton("No", callback_data="delete_no"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"❓ Are you sure you want to delete alert ID {alert_id}?",
            reply_markup=reply_markup,
        )

    # Callback query handler to process the button clicks
    async def button_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        await query.answer()

        if query.data.startswith("delete_yes_"):
            alert_id = int(query.data.split("_")[2])

            async with aiofiles.open("alert_list.txt", "r") as f:
                alerts = await f.readlines()

            async with aiofiles.open("alert_list.txt", "w") as f:
                for i, alert in enumerate(alerts):
                    if i + 1 != alert_id:
                        await f.write(alert)

            await query.edit_message_text(f"✅ Alert ID {alert_id} deleted")
        elif query.data == "delete_no":
            await query.edit_message_text("❌ Deletion cancelled")

    async def monitor_alerts(self, context: ContextTypes.DEFAULT_TYPE):
        """
        Background task to monitor price alerts.
        Checks if current prices are within threshold of alert prices.
        """
        try:
            # Read alerts from file
            async with aiofiles.open("alert_list.txt", "r") as f:
                alerts = await f.readlines()

            if not alerts:
                return

            # Create price bot instance
            price_bot = CryptoPriceBot()

            # Check each alert
            for alert in alerts:
                try:
                    symbol, target_price = alert.strip().split(",")
                    target_price = float(target_price)

                    # Get current price
                    ticker_data = await price_bot.fetch_latest_price(symbol)
                    if not ticker_data:
                        continue

                    current_price = ticker_data["current_price"]

                    # Calculate price difference percentage
                    price_diff_pct = abs(current_price - target_price) / target_price
                    # If price is within threshold, send alert
                    if price_diff_pct <= self.price_threshold:
                        alert_message = (
                            f"🚨 Price Alert!\n"
                            f"Symbol: {symbol}\n"
                            f"Target: ${target_price:,.4f}\n"
                            f"Current: ${current_price:,.4f}\n"
                            f"Difference: {price_diff_pct:.4f}%\n"
                            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                        )
                        # Send alert to all active chats
                        if context._chat_id:
                            await self.application.bot.send_message(
                                chat_id=context._chat_id, text=alert_message
                            )

                except Exception as e:
                    print(f"Error processing alert {alert}: {str(e)}")
                    continue

            # Close price bot
            await price_bot.close()

        except Exception as e:
            print(f"Error in monitor_alerts: {str(e)}")

    def run(self):
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)
