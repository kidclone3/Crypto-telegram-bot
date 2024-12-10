from telethon import TelegramClient, events

from src.core.config import settings
from .parser import QUERY_PATTERN, parser

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


@bot.on(events.NewMessage(pattern="/a"))
async def add_alert(event):
    await event.reply("Adding alert")
