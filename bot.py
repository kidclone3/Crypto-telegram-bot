from src.services.monitor_service import MonitorService
from src.services.bot import bot, db, loop
from src.services.monitor_signal import SignalService
import asyncio

import asyncio
import signal as sys_signal
import sys


async def shutdown(signal, loop, monitor, signal_service):
    """Cleanup tasks tied to the service's shutdown."""
    print(f"Received exit signal {signal.name}...")

    # First stop the services to prevent new task creation
    await monitor.stop_monitoring()
    await signal_service.stop_monitoring()

    # Get all running tasks except the shutdown task itself
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    print(f"Cancelling {len(tasks)} outstanding tasks")

    # Cancel all tasks
    for task in tasks:
        task.cancel()

    # Wait for all tasks to complete with a timeout
    try:
        await asyncio.wait(tasks, timeout=5)
    except asyncio.CancelledError:
        pass

    # Stop the loop
    loop.stop()


async def main():
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

    try:
        # Start the monitoring services
        monitoring_task = asyncio.create_task(signal_service.start_monitoring())
        monitor_task = asyncio.create_task(monitor.start_monitoring())

        # Run the bot
        await bot.run_until_disconnected()

    except Exception as e:
        print(f"Error occurred: {e}")
        raise
    finally:
        await shutdown(sys_signal.SIGTERM, loop, monitor, signal_service)


if __name__ == "__main__":
    while True:
        try:
            loop.run_until_complete(main())
        except (KeyboardInterrupt, Exception) as e:
            print("Received keyboard interrupt, shutting down...")
            break
        except Exception as e:
            print(f"Error occurred: {e}. Restarting services...")
        finally:
            try:
                loop.close()
            except Exception as e:
                print(f"Error closing loop: {e}")

            # Create a new event loop for the next iteration
            if not loop.is_closed():
                loop.close()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
