from pyrogram import Client, filters
from clones.helpers import (
    ACTIVE_CLONES, check_user_subscribed, log_new_user_start,
    log_download_action, handle_auto_delete_if_enabled
)
from clones.tree import start_clone_bot, stop_clone_bot, show_user_tree
from clones.handlers import clone_start_handler, clone_id_handler, clone_explore_handler, clone_available_series_handler
from clones.callbacks import clone_callback_handler

def register_clone_handlers(app: Client):
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

    @app.on_callback_query()
    async def cb_query(client: Client, callback):
        await clone_callback_handler(client, callback)
