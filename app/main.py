import asyncio
import threading

from ruzbot import bot
from daily_timer import timerPooling

async def startBot():
    await bot.polling()
    
async def startTimer():
    await timerPooling()
    
async def main():
    """
    Main entry point of the program.

    This function starts the bot.
    """
    
    # Creating tasks for bot and timer
    bot_task = asyncio.create_task(startBot())
    timer_task = asyncio.create_task(startTimer())
    
    await bot_task
    await timer_task
    
if __name__ == "__main__":
    asyncio.run(main())
