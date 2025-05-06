from src.services.monitor_service import MonitorService
from src.services.monitor_signal import SignalService
from src.utils.logger import logger
import asyncio
import signal as sys_signal
from src.bot.telegram_bot import bot, db, initialize_and_start_bot


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
    if (
        loop and not loop.is_closed() and loop.is_running()
    ):  # Check if loop is running before stopping
        loop.stop()
    logger.info("Event loop stopped or was already stopped")


async def main():
    logger.info("Starting main application")
    current_loop = asyncio.get_running_loop()  # ADDED: Get current running loop

    # Create the services
    monitor = MonitorService(db, bot)
    signal_service = SignalService(db, bot)

    # Setup shutdown handler
    for sig in (sys_signal.SIGTERM, sys_signal.SIGINT):
        current_loop.add_signal_handler(  # MODIFIED: Use current_loop
            sig,
            lambda s=sig: asyncio.create_task(
                shutdown(
                    s, current_loop, monitor, signal_service
                )  # MODIFIED: Pass current_loop
            ),
        )
    logger.info("Shutdown handlers configured")

    try:
        # Start the monitoring services
        logger.info("Starting monitoring services")
        monitoring_task = asyncio.create_task(signal_service.start_monitoring())
        monitor_task = asyncio.create_task(monitor.start_monitoring())

        # Initialize and Start the bot
        logger.info("Initializing and starting Telegram bot")  # ADDED
        await initialize_and_start_bot()  # ADDED: Initialize and start the bot

        # Run the bot
        logger.info("Running Telegram bot until disconnected")  # MODIFIED: Log message
        await bot.run_until_disconnected()

    except Exception as e:
        logger.error(f"Error occurred in main loop: {str(e)}", exc_info=True)
        raise
    finally:
        logger.info("Initiating shutdown sequence in main() finally block")
        await shutdown(
            sys_signal.SIGTERM, current_loop, monitor, signal_service
        )  # MODIFIED: Pass current_loop


# The if __name__ == "__main__": block below has its own loop management.
# This can conflict with asyncio.run() from the root main.py.
# This block is left as is for now, but might need refactoring
# if src/main.py is not intended to be a standalone entry point
# or if it causes issues with the primary entry point.
if __name__ == "__main__":
    logger.info("Application started directly via src/main.py")
    # This loop management is specific to direct execution of src/main.py
    # and is different from how the root main.py (using asyncio.run) manages the loop.
    # This could be a source of confusion or conflict.
    local_loop = asyncio.new_event_loop()  # Use a distinct variable name
    asyncio.set_event_loop(local_loop)
    try:
        local_loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt in src/main.py, shutting down...")
    except Exception as e:
        logger.error(
            f"Error occurred in src/main.py: {str(e)}. Restarting services...",
            exc_info=True,
        )  # This restart logic is complex
    finally:
        logger.info("Closing loop in src/main.py finally block")
        if not local_loop.is_closed():
            # Cancel all remaining tasks on this specific loop before closing
            for task in asyncio.all_tasks(loop=local_loop):
                task.cancel()
            # Give tasks a chance to cancel
            # Shield the gather from being cancelled itself if the loop is stopping
            try:
                # Wait for tasks to cancel, but don't let gather itself be cancelled by loop.stop()
                # This is tricky; a simpler approach might be needed if issues persist.
                async def wait_for_tasks():
                    await asyncio.gather(
                        *[
                            task
                            for task in asyncio.all_tasks(loop=local_loop)
                            if task is not asyncio.current_task()
                        ],
                        return_exceptions=True,
                    )

                local_loop.run_until_complete(wait_for_tasks())
            except Exception as e_gather:
                logger.error(f"Error during task gathering for loop close: {e_gather}")

            local_loop.close()
        logger.info("Loop closed in src/main.py")
    # The restart logic by creating a new loop here is highly problematic for Telethon
    # and is likely the original source of the event loop change error if this file was run directly
    # or if its loop management interfered.
    # For the primary execution path (root main.py), this block is not hit initially.
    # Removing the while True and subsequent loop recreation for now as it's complex and error-prone.
    # If restart logic is needed, it should be handled more robustly.
    logger.info("src/main.py direct execution finished.")
