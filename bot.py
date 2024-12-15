from src.services.monitor_service import MonitorService
from src.services.bot import bot, db, loop

if __name__ == "__main__":
    monitor = MonitorService(db, bot)
    loop.create_task(monitor.start_monitoring())
    try:
        bot.run_until_disconnected()
    finally:
        loop.run_until_complete(monitor.stop_monitoring())
        loop.close()
