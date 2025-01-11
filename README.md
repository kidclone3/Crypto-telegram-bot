# Crypto Telegram Bot
Web telegram client with API interface. Python + FastAPI + Telethon.

# Installation
Use poetry to install dependencies.
```bash
poetry install
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
- [x] Store user data in MongoDB

## Microservices:
- [ ] Store fetched data in InfluxDB
- [ ] Use ai agent, sent sentiment analysis to users with message queue

