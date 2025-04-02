# Crypto Price Bot Commands

## Inline Mode
You can use this bot in any chat by typing `@Tes1241t_bot` followed by your query. The bot supports:

- **Price Queries**: Type a cryptocurrency symbol (e.g., `@Tes1241t_bot BTC/USDT`)
- **AI Queries**: Ask any question about crypto (e.g., `@Tes1241t_bot What's the current market sentiment?`)
- **Quick Access**: Get instant access to Fear & Greed Index and News

## Basic Commands
- `/start` - Show welcome message
- `/help` - Show help message
- `/ping` - Check if the bot is online

## Price & Alerts
### Alert Management
- `/a` or `/alert` - Manage price alerts
  ```
  /a BTC 1000000 - Set alert on BTC at 100k
  /a - List all active alerts
  ```
- `/dela` or `/delete_alert` - Delete a price alert
  ```
  /dela 1 - Delete alert with ID 1
  ```
- `/p` or `/price` - Get current price
  ```
  /p BTC/USDT
  ```

## Technical Analysis
- `/f` or `/filter` - Filter price changes by timeframe and percentage
  ```
  /f 15m 1 - Show coins with 1% change in 15 minutes
  ```
- `/c` or `/chart` - Get price chart for a cryptocurrency
  ```
  /c BTC/USDT 4h - Get 4-hour chart
  Available timeframes: 1m, 5m, 15m, 1h, 4h, 1d
  ```
- `/s` or `/signal` - Get trading signal for a cryptocurrency
  ```
  /s BTC 1h - Get 1-hour trading signals
  ```

## Market Monitoring
- `/mon` or `/monitor` - Manage symbol monitoring
  ```
  /mon BTC ETH - Monitor BTC and ETH
  /mon - List all monitored symbols
  ```
- `/delmon` or `/delete_monitor` - Delete a monitor
  ```
  /delmon 1 - Delete monitor with ID 1
  ```
- `/calendar` - Get economic calendar events
- `/news` - Get latest news
- `/feargreed` - Get the current Crypto Fear & Greed Index
- `/llm` - Send a prompt to the LLM
  ```
  /llm What's the current price of Bitcoin?
  ```

## Configuration
- `/config` - View or update bot settings
  ```
  /config is_alert on/off
  /config price_threshold 0.01
  /config alert_interval 1
  /config is_future on/off
  ``` 