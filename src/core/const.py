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
