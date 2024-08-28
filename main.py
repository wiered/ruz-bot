import asyncio

from ruzbot import bot

def main():
    """
    Main entry point of the program.

    This function starts the bot.
    """
    # Run the bot using asyncio
    asyncio.run(bot.polling())
    
if __name__ == "__main__":
    main()
