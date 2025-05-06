import os
import sys
import asyncio
import uvicorn
from src.utils.logger import logger
from src.main import main as bot_main
from src.api.v1.endpoints.app import app as api_app


async def run_bot():
    """Run the Telegram bot service"""
    try:
        await bot_main()
    except Exception as e:
        logger.error(f"Bot service error: {str(e)}", exc_info=True)
        raise


async def run_api():
    """Run the FastAPI service"""
    try:
        config = uvicorn.Config(
            api_app,
            host="0.0.0.0",
            port=8000,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()
    except Exception as e:
        logger.error(f"API service error: {str(e)}", exc_info=True)
        raise


async def main():
    """Main entry point that runs both services concurrently"""
    logger.info("Starting application services...")
    
    # Create tasks for both services
    bot_task = asyncio.create_task(run_bot())
    api_task = asyncio.create_task(run_api())
    
    try:
        # Wait for both tasks to complete
        await asyncio.gather(bot_task, api_task)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Application error: {str(e)}", exc_info=True)
        raise
    finally:
        logger.info("Shutting down application...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True) 