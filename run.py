import asyncio
import sys
from pyrogram import Client
from main_bot import register_main_bot_handlers
from clone_bot import start_clone_bot, stop_clone_bot, ACTIVE_CLONES
import database
from config import MAIN_BOT_TOKEN, API_ID, API_HASH

async def main():
    print("Initializing Database...")
    database.db_init()
    
    print("Starting Main Bot...")
    main_bot = Client(
        name="main_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=MAIN_BOT_TOKEN,
        in_memory=True
    )
    register_main_bot_handlers(main_bot)
    await main_bot.start()
    
    main_me = await main_bot.get_me()
    print(f"Main Bot started successfully: @{main_me.username}")
    
    # Auto-start active clone bots from database
    print("Loading active clone bots from database...")
    clone_bots = await database.get_clone_bots()
    started_clones = 0
    for b in clone_bots:
        if b["is_active"]:
            print(f"Starting active clone bot: @{b['username']}...")
            success = await start_clone_bot(b["token"])
            if success:
                started_clones += 1
            else:
                # Update status to inactive in DB if it failed to start (e.g. revoked token)
                await database.set_clone_bot_status(b["token"], False)
                
    print(f"Clone bots loaded. Concurrently active: {started_clones}")
    print("System is fully running. Press CTRL+C to stop.")
    
    # Block and run until interrupted
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        print("\nStopping all bots gracefully...")
        # Stop Main Bot
        try:
            await main_bot.stop()
            print("Main Bot stopped.")
        except Exception as e:
            print(f"Error stopping Main Bot: {e}")
            
        # Stop all clone bots
        tokens = list(ACTIVE_CLONES.keys())
        for token in tokens:
            print(f"Stopping clone bot client...")
            await stop_clone_bot(token)
            
        print("All bot processes terminated. System offline.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSystem execution interrupted. Exiting.")
        sys.exit(0)
