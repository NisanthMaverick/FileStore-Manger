import json
from pyrogram import Client
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
import database
from .helpers import (
    ADMIN_STATES, get_back_button
)
from .ui_config import (
    show_bot_config, show_auto_delete_menu, show_fsub_menu,
    show_fsub_ch_details, show_btn_mgr, show_btn_details
)

async def handle_config_callbacks(client: Client, callback: CallbackQuery, data: str) -> bool:
    user_id = callback.from_user.id

    if data == "bot_config":
        await callback.answer()
        await show_bot_config(client, callback.message.chat.id, callback.message.id)
        return True

    elif data == "edit_welcome":
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_welcome", "message_id": callback.message.id}
        await callback.message.edit_text(
            "📝 **Customize Welcome Message**\n\nYou can use the following placeholders:\n"
            "▪️ `{mention}`: Mentions the user.\n"
            "▪️ `{first_name}`: User's first name.\n"
            "▪️ `{bot_name}`: This bot's name.\n"
            "▪️ `{bot_link}`: Bot's Telegram link.\n"
            "▪️ `{mentionbot}`: Mentions the bot.\n\n"
            "Send your new welcome message template:\n\n❌ Send /cancel to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="bot_config")]])
        )
        return True

    elif data == "fsub_menu":
        await callback.answer()
        await show_fsub_menu(client, callback.message.chat.id, callback.message.id)
        return True

    elif data == "toggle_fsub":
        settings = await database.get_settings()
        new_status = not settings.get("fsub_enabled")
        await database.update_settings({"fsub_enabled": new_status})
        await callback.answer(f"Force-Subscribe toggled to: {'Enabled' if new_status else 'Disabled'}")
        await show_fsub_menu(client, callback.message.chat.id, callback.message.id)
        return True

    elif data == "add_fsub_channel":
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_fsub_channel", "message_id": callback.message.id}
        await callback.message.edit_text(
            "📢 **Add FSub Channel**\n\n1. Add this bot as an **Administrator** in the target channel.\n"
            "2. Forward any message from the channel here, or paste the channel username/ID.\n\n❌ Send /cancel to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="fsub_menu")]])
        )
        return True

    elif data.startswith("fsub_ch_"):
        await callback.answer()
        idx = int(data.replace("fsub_ch_", ""))
        await show_fsub_ch_details(client, callback.message.chat.id, callback.message.id, idx)
        return True

    elif data.startswith("fsub_del_ch_"):
        idx = int(data.replace("fsub_del_ch_", ""))
        settings = await database.get_settings()
        raw_channels = settings.get("fsub_channels") or ""
        channels_list = []
        try:
            channels_list = json.loads(raw_channels)
        except Exception:
            pass
        
        if 0 <= idx < len(channels_list):
            removed_ch = channels_list.pop(idx)
            await database.update_settings({"fsub_channels": json.dumps(channels_list)})
            await callback.answer(f"Removed FSub Channel: {removed_ch.get('title')}", show_alert=True)
        
        await show_fsub_menu(client, callback.message.chat.id, callback.message.id)
        return True

    elif data.startswith("fsub_edit_link_"):
        await callback.answer()
        idx = int(data.replace("fsub_edit_link_", ""))
        ADMIN_STATES[user_id] = {
            "state": "waiting_for_fsub_edit_link",
            "message_id": callback.message.id,
            "data": {"index": idx}
        }
        await callback.message.edit_text(
            "✏️ **Edit Invite Link**\n\nPlease enter the new invite link for this channel:\n\n❌ Send /cancel to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data=f"fsub_ch_{idx}")]])
        )
        return True

    elif data == "btn_mgr":
        await callback.answer()
        await show_btn_mgr(client, callback.message.chat.id, callback.message.id)
        return True

    elif data == "add_btn":
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_btn_name", "message_id": callback.message.id}
        await callback.message.edit_text(
            "🔘 **Add Custom Button**\n\nPlease enter the **Button Name / Label**:\n\n❌ Send /cancel to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="btn_mgr")]])
        )
        return True

    elif data.startswith("btn_details_"):
        await callback.answer()
        idx = int(data.replace("btn_details_", ""))
        await show_btn_details(client, callback.message.chat.id, callback.message.id, idx)
        return True

    elif data.startswith("btn_edit_link_"):
        await callback.answer()
        idx = int(data.replace("btn_edit_link_", ""))
        ADMIN_STATES[user_id] = {
            "state": "waiting_for_btn_edit_link",
            "message_id": callback.message.id,
            "data": {"index": idx}
        }
        await callback.message.edit_text(
            "✏️ **Edit Custom Button URL**\n\nPlease enter the new URL link for this button:\n\n❌ Send /cancel to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data=f"btn_details_{idx}")]])
        )
        return True

    elif data.startswith("btn_delete_"):
        idx = int(data.replace("btn_delete_", ""))
        settings = await database.get_settings()
        buttons_list = json.loads(settings.get("custom_buttons", "[]"))
        
        if 0 <= idx < len(buttons_list):
            removed_btn = buttons_list.pop(idx)
            await database.update_settings({"custom_buttons": json.dumps(buttons_list)})
            await callback.answer(f"Removed Button: {removed_btn['text']}", show_alert=True)
        
        await show_btn_mgr(client, callback.message.chat.id, callback.message.id)
        return True

    elif data == "auto_delete_menu":
        await callback.answer()
        await show_auto_delete_menu(client, callback.message.chat.id, callback.message.id)
        return True

    elif data == "toggle_auto_delete":
        settings = await database.get_settings()
        new_status = not settings.get("auto_delete_enabled", False)
        await database.update_settings({"auto_delete_enabled": new_status})
        await callback.answer(f"Auto-delete toggled to: {'Enabled' if new_status else 'Disabled'}")
        await show_auto_delete_menu(client, callback.message.chat.id, callback.message.id)
        return True

    elif data == "edit_auto_delete_duration":
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_auto_delete_duration", "message_id": callback.message.id}
        await callback.message.edit_text(
            "⏳ **Edit Auto Delete Duration**\n\nPlease enter the duration in minutes after which files will be deleted automatically (e.g. `5`):\n\n❌ Send /cancel to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="auto_delete_menu")]])
        )
        return True

    return False
