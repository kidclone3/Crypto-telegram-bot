from src.services.monitor_service import MonitorService
from src.services.bot import bot, db, loop
from src.services.monitor_signal import SignalService
from src.utils.logger import logger
import asyncio
import signal as sys_signal


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
    loop.stop()
    logger.info("Event loop stopped")


async def main():
    logger.info("Starting main application")
    # Create the services
    monitor = MonitorService(db, bot)
    signal_service = SignalService(db, bot)

    # Setup shutdown handler
    for sig in (sys_signal.SIGTERM, sys_signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(
                shutdown(s, loop, monitor, signal_service)
            ),
        )
    logger.info("Shutdown handlers configured")

    try:
        # Start the monitoring services
        logger.info("Starting monitoring services")
        monitoring_task = asyncio.create_task(signal_service.start_monitoring())
        monitor_task = asyncio.create_task(monitor.start_monitoring())

        # Run the bot
        logger.info("Starting Telegram bot")
        await bot.run_until_disconnected()

    except Exception as e:
        logger.error(f"Error occurred in main loop: {str(e)}", exc_info=True)
        raise
    finally:
        logger.info("Initiating shutdown sequence")
        await shutdown(sys_signal.SIGTERM, loop, monitor, signal_service)


if __name__ == "__main__":
    logger.info("Application started")
    while True:
        try:
            loop.run_until_complete(main())
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down...")
            break
        except Exception as e:
            logger.error(f"Error occurred: {str(e)}. Restarting services...", exc_info=True)
        finally:
            try:
                loop.close()
            except Exception as e:
                logger.error(f"Error closing loop: {str(e)}", exc_info=True)

            # Create a new event loop for the next iteration
            if not loop.is_closed():
                loop.close()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            logger.info("New event loop created")
