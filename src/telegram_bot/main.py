import asyncio
import signal as sys_signal

from telegram_bot.bootstrap import bootstrap
from telegram_bot.utils.logger import logger


async def run_bot():
    """Run the Telegram bot service merged from main.py."""
    try:
        await main()
    except Exception as e:
        logger.error(f"Bot service error: {str(e)}", exc_info=True)
        raise


async def shutdown(signal, loop):
    """Cleanup tasks tied to the service's shutdown."""
    logger.info(f"Received exit signal {signal.name}...")
    await bootstrap.monitor_service.stop_monitoring()
    await bootstrap.signal_service.stop_monitoring()
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    logger.info(f"Cancelling {len(tasks)} outstanding tasks")
    for task in tasks:
        task.cancel()
    try:
        await asyncio.wait(tasks, timeout=5)
    except asyncio.CancelledError:
        logger.warning("Some tasks were cancelled during shutdown")
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")
    # Removed loop.stop() to avoid premature event loop shutdown
    logger.info("Event loop stopped or was already stopped")


async def main():
    logger.info("Starting main application")
    current_loop = asyncio.get_running_loop()
    for sig in (sys_signal.SIGTERM, sys_signal.SIGINT):
        current_loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(shutdown(s, current_loop)),
        )
    logger.info("Shutdown handlers configured")
    try:
        logger.info("Starting monitoring services")
        monitoring_task = asyncio.create_task(
            bootstrap.signal_service.start_monitoring()
        )
        monitor_task = asyncio.create_task(
            bootstrap.monitor_service.start_monitoring()
        )
        logger.info("Initializing and starting Telegram bot")
        await bootstrap.initialize_bot()
        logger.info("Waiting for Telegram bot to disconnect")
        await bootstrap.telegram_bot.disconnected
    except Exception as e:
        logger.error(f"Error occurred in main loop: {str(e)}", exc_info=True)
        raise
    finally:
        logger.info("Initiating shutdown sequence in main() finally block")
        await shutdown(sys_signal.SIGTERM, current_loop)


if __name__ == "__main__":
    logger.info("Application started")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Error occurred in src/main.py: {str(e)}", exc_info=True)
