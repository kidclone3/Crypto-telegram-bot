# Crypto Telegram Bot
Web telegram client with API interface. Python + FastAPI + Telethon.

# Installation
```bash
pip install -r requirements.txt
```

# Usage
```bash
python bot.py
```
or use `watchmedo` to auto-restart the bot on file changes.
```bash
watchmedo auto-restart --directory=./src --pattern='*.py' --recursive -- python -u bot.py
```


### Tech Stack:
- Python 3.12
- FastAPI
- MongoDB
- Telethon
- InfluxDB


# Features:

- [x] Real time price alerts
- [ ] Use tradingview charting library
- [ ] Store user data in MongoDB
- [ ] Store fetched data in InfluxDB
