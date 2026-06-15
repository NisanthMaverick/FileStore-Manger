from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
import database
from config import OWNER_ID
from .helpers import (
    ADMIN_STATES, get_main_panel_markup, get_welcome_markup, log_new_user_start, get_back_button
)

async def start_handler(client: Client, message: Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    username = message.from_user.username
    
    # Force sync user premium status with remote DB on start command (bypassing cache lags)
    await database.sync_single_premium_user(user_id)
    
    # Save user to DB
    is_new = await database.add_user(user_id, username, first_name)
    if is_new:
        await log_new_user_start(client, message)
    
    # Extract payload if any
    payload = message.text.split(" ", 1)[1] if len(message.text.split(" ", 1)) > 1 else ""

    is_premium = await database.is_premium_user(user_id, OWNER_ID)
    is_user_admin = await database.is_admin(user_id, OWNER_ID)

    # If payload is empty or a premium activation payload, handle premium verification messages
    if not payload or payload == "premium" or payload.startswith("premium_"):
        if is_premium and not is_user_admin:
            msg_text = (
                "🎉 **Premium VIP Access Activated!** 🎉\n\n"
                "Your premium subscription is active. You now have full access to this bot.\n\n"
                "🚀 Use /explorefiles or search for files directly to start downloading!"
            )
            await message.reply_text(msg_text, disable_web_page_preview=True)
            return
        elif payload == "premium" or payload.startswith("premium_"):
            await message.reply_text(
                "❌ **Premium Activation Failed**\n\n"
                "We could not verify an active premium subscription for your account.\n"
                "If you recently paid, please wait a moment for approval or contact admin."
            )
            return

    if payload == "availableseries":
        await master_available_series_handler(client, message)
        return

    # Check if user is admin
    if not is_user_admin:
        settings = await database.get_settings()
        welcome_text = settings.get("welcome_msg") or "Hey {mention}, welcome to {bot_name}!"
        bot_me = client.me
        welcome_text = welcome_text.format(
            mention=message.from_user.mention,
            first_name=message.from_user.first_name,
            bot_name=bot_me.first_name,
            bot_link=f"https://t.me/{bot_me.username}",
            mention_bot=f"[{bot_me.first_name}](tg://user?id={bot_me.id})",
            mentionbot=f"[{bot_me.first_name}](tg://user?id={bot_me.id})"
        )
        markup = await get_welcome_markup()
        return await message.reply_text(welcome_text, reply_markup=markup)


    # Admin start flow
    await message.reply_text(
        "🛠 **Master Admin Control Panel** 🛠\n\nSelect a category below to configure and manage the bot:",
        reply_markup=get_main_panel_markup()
    )

async def master_available_series_handler(client: Client, message: Message):
    user_id = message.from_user.id
    is_user_admin = await database.is_admin(user_id, OWNER_ID)
    if is_user_admin:
        series_list = await database.list_series()
        if not series_list:
            await message.reply_text("🎬 **No series available at the moment.**")
            return
        text = "🎬 **Available Series Library** 🎬\n━━━━━━━━━━━━━━━━━━━━\n\nHere are the series currently available in the system:\n\n"
        for s in series_list:
            text += f"▪️ **{s['title']}**\n"
            if s.get('description'):
                text += f"   └ _{s['description']}_\n"
            text += "\n"
        buttons = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="welcome_back")]]
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        settings = await database.get_settings()
        primary = settings.get("primary_clone_username")
        if primary:
            clean_primary = primary.lstrip("@")
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("Go to Series Bot 🤖", url=f"https://t.me/{clean_primary}?start=availableseries")]])
            await message.reply_text(
                "🎬 **Available Series List**\n\n"
                "To view and download our series collection, please use our main clone bot by clicking the button below:",
                reply_markup=markup
            )
        else:
            await message.reply_text("Browse features are only available in clone bots. Please contact admin to get a clone bot link.")

async def cancel_handler(client: Client, message: Message):
    user_id = message.from_user.id
    is_user_admin = await database.is_admin(user_id, OWNER_ID)
    if not is_user_admin:
        return

    if user_id in ADMIN_STATES:
        ADMIN_STATES.pop(user_id)
        await message.reply_text("❌ Action cancelled. State cleared.", reply_markup=get_main_panel_markup())
    else:
        await message.reply_text("No active action to cancel.", reply_markup=get_main_panel_markup())

async def id_handler(client: Client, message: Message):
    user_id = message.from_user.id
    await message.reply_text(f"🆔 **Your Telegram ID:** `{user_id}`")

async def explore_handler(client: Client, message: Message):
    user_id = message.from_user.id
    is_admin = await database.is_admin(user_id, OWNER_ID)
    if is_admin:
        series_list = await database.list_series()
        text = "🎬 **Video Series Library**\n\nSelect a series to browse:\n\n"
        buttons = []
        if not series_list:
            text += "_No series created yet._"
        else:
            for s in series_list:
                buttons.append([
                    InlineKeyboardButton(f"🎬 {s['title']}", callback_data=f"browse_sec_{s['id']}_0")
                ])
        buttons.append(get_back_button("manage_files"))
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        settings = await database.get_settings()
        primary = settings.get("primary_clone_username")
        if primary:
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("Go to Bot 🤖", url=f"https://t.me/{primary}")]])
            await message.reply_text("Select a clone bot below to browse files:", reply_markup=markup)
        else:
            await message.reply_text("Browse features are only available in the clone bots. Please contact admin to get a clone bot link.")
