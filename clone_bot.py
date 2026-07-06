from pyrogram import Client, filters
from clones.helpers import (
    ACTIVE_CLONES, check_user_subscribed, log_new_user_start,
    log_download_action, handle_auto_delete_if_enabled
)
from clones.tree import start_clone_bot, stop_clone_bot, show_user_tree
from clones.handlers import clone_start_handler, clone_id_handler, clone_explore_handler, clone_available_series_handler, clone_info_handler
from clones.callbacks import clone_callback_handler

import database

def register_clone_handlers(app: Client):
    @app.on_message(filters.private, group=-1)
    async def block_testing_messages(client: Client, message):
        user_id = message.from_user.id if message.from_user else None
        if not user_id:
            return
        from config import OWNER_ID
        is_admin = await database.is_admin(user_id, OWNER_ID)
        if is_admin:
            return
        settings = await database.get_settings()
        if settings.get("testing_mode", False):
            await database.add_user(user_id, message.from_user.username or "", message.from_user.first_name or "")
            await message.reply_text(
                "⚠️ **Testing Mode Active**\n\n"
                "This bot is currently in user testing mode as we are adding new features. "
                "Once it is open, you can use it. Please come back and try again after some time."
            )
            message.stop_propagation()

    @app.on_callback_query(group=-1)
    async def block_testing_callbacks(client: Client, callback):
        user_id = callback.from_user.id if callback.from_user else None
        if not user_id:
            return
        from config import OWNER_ID
        is_admin = await database.is_admin(user_id, OWNER_ID)
        if is_admin:
            return
        settings = await database.get_settings()
        if settings.get("testing_mode", False):
            await callback.answer(
                "⚠️ This bot is currently in user testing mode as we are adding new features. "
                "Once it is open, you can use it. Please come back and try again after some time.",
                show_alert=True
            )
            callback.stop_propagation()

    @app.on_message(filters.command("start") & filters.private)
    async def start_cmd(client: Client, message):
        await clone_start_handler(client, message)

    @app.on_message(filters.command("id") & filters.private)
    async def id_cmd(client: Client, message):
        await clone_id_handler(client, message)

    @app.on_message(filters.command("explorefiles") & filters.private)
    async def explore_cmd(client: Client, message):
        await clone_explore_handler(client, message)

    @app.on_message(filters.command("availableseries") & filters.private)
    async def avail_series_cmd(client: Client, message):
        await clone_available_series_handler(client, message)

    @app.on_message(filters.command("info") & filters.private)
    async def info_cmd(client: Client, message):
        await clone_info_handler(client, message)

    @app.on_callback_query()
    async def cb_query(client: Client, callback):
        await clone_callback_handler(client, callback)
