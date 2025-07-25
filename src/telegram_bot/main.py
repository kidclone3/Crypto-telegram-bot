import asyncio
import signal as sys_signal

from telegram_bot.bot.telegram_bot import bot, db, initialize_and_start_bot
from telegram_bot.services.monitor_service import MonitorService
from telegram_bot.services.monitor_signal import SignalService
from telegram_bot.utils.logger import logger


async def run_bot():
    """Run the Telegram bot service merged from main.py.

    This function wraps the main application logic and provides
    error handling as seen in the original main.py.
    """
    try:
        await main()
    except Exception as e:
        logger.error(f"Bot service error: {str(e)}", exc_info=True)
        raise


async def shutdown(signal, loop, monitor, signal_service):
    """Cleanup tasks tied to the service's shutdown."""
    logger.info(f"Received exit signal {signal.name}...")
    # First stop the services to prevent new task creation
    await monitor.stop_monitoring()
    await signal_service.stop_monitoring()
    # Get all running tasks except the shutdown task itself
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    logger.info(f"Cancelling {len(tasks)} outstanding tasks")
    # Cancel all tasks
    for task in tasks:
        task.cancel()
    # Wait for all tasks to complete with a timeout
    try:
        await asyncio.wait(tasks, timeout=5)
    except asyncio.CancelledError:
        logger.warning("Some tasks were cancelled during shutdown")
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")
    # Stop the loop
    if loop and not loop.is_closed() and loop.is_running():
        loop.stop()
    logger.info("Event loop stopped or was already stopped")


async def main():
    logger.info("Starting main application")
    current_loop = asyncio.get_running_loop()  # Get current running loop
    # Create the services
    monitor = MonitorService(db, bot)
    signal_service = SignalService(db, bot)
    # Setup shutdown handler
    for sig in (sys_signal.SIGTERM, sys_signal.SIGINT):
        current_loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(
                shutdown(s, current_loop, monitor, signal_service)
            ),
        )
    logger.info("Shutdown handlers configured")
    try:
        # Start the monitoring services
        logger.info("Starting monitoring services")
        monitoring_task = asyncio.create_task(signal_service.start_monitoring())
        monitor_task = asyncio.create_task(monitor.start_monitoring())
        # Initialize and start the bot
        logger.info("Initializing and starting Telegram bot")
        await initialize_and_start_bot()
        # Run the bot in a thread to avoid blocking the async loop
        logger.info("Running Telegram bot until disconnected")
        await bot.disconnected
    except Exception as e:
        logger.error(f"Error occurred in main loop: {str(e)}", exc_info=True)
        raise
    finally:
        logger.info("Initiating shutdown sequence in main() finally block")
        await shutdown(
            sys_signal.SIGTERM, current_loop, monitor, signal_service
        )


if __name__ == "__main__":
    logger.info("Application started")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Error occurred in src/main.py: {str(e)}", exc_info=True)
