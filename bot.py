from src.services.monitor_service import MonitorService
from src.services.bot import bot, db, loop
from src.services.monitor_signal import SignalService
import asyncio

if __name__ == "__main__":
    while True:
        try:
            monitor = MonitorService(db, bot)
            signal = SignalService(db, bot)
            loop.create_task(signal.start_monitoring())
            loop.create_task(monitor.start_monitoring())
            bot.run_until_disconnected()
        except Exception as e:
            print(f"Error occurred: {e}. Restarting services...")
        finally:
            loop.run_until_complete(monitor.stop_monitoring())
            loop.run_until_complete(signal.stop_monitoring())
            loop.close()
            loop = asyncio.get_event_loop()  # Recreate the event loop
