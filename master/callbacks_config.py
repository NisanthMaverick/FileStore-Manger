import json
from pyrogram import Client
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
import database
from .helpers import (
    ADMIN_STATES, get_back_button
)
from .ui_config import (
    show_bot_config, show_auto_delete_menu, show_fsub_menu,
    show_fsub_ch_details, show_btn_mgr, show_btn_details,
    show_start_end_msg_menu
)

async def handle_config_callbacks(client: Client, callback: CallbackQuery, data: str) -> bool:
    user_id = callback.from_user.id

    if data == "bot_config":
        await callback.answer()
        await show_bot_config(client, callback.message.chat.id, callback.message.id)
        return True

    elif data == "edit_user_send_delay":
        await callback.answer()
        settings = await database.get_settings()
        current_delay = settings.get("user_send_delay", 3)
        ADMIN_STATES[user_id] = {"state": "waiting_for_user_send_delay", "message_id": callback.message.id}
        await callback.message.edit_text(
            "⏱ **Edit User File Delivery Delay**\n\n"
            "Enter the delay time in seconds (integer between `0` and `10`) to wait between sending files to a user.\n\n"
            "Type `no` to disable delay (set to `0` seconds).\n\n"
            f"Current Delay: `{current_delay}` second(s)\n"
            "Default: `3` seconds\n"
            "Max: `10` seconds\n\n"
            "❌ Send `/cancel` to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="bot_config")]])
        )
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

    elif data == "start_end_msg_menu":
        await callback.answer()
        await show_start_end_msg_menu(client, callback.message.chat.id, callback.message.id)
        return True

    elif data == "toggle_start_end_msg":
        settings = await database.get_settings()
        new_status = not settings.get("start_end_msg_enabled", False)
        await database.update_settings({"start_end_msg_enabled": new_status})
        await callback.answer(f"Start/End Messages toggled to: {'Enabled' if new_status else 'Disabled'}")
        await show_start_end_msg_menu(client, callback.message.chat.id, callback.message.id)
        return True

    elif data == "set_start_msg":
        settings = await database.get_settings()
        if not settings.get("db_channel_id"):
            await callback.answer("❌ Please configure DB Storage Channel first!", show_alert=True)
            return True
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_start_msg", "message_id": callback.message.id}
        await callback.message.edit_text(
            "📤 **Set Start Message**\n\nPlease send or forward the message you want to set as the **Start Message**. It can be text, sticker, photo, video, etc.\n\n❌ Send /cancel to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="start_end_msg_menu")]])
        )
        return True

    elif data == "set_end_msg":
        settings = await database.get_settings()
        if not settings.get("db_channel_id"):
            await callback.answer("❌ Please configure DB Storage Channel first!", show_alert=True)
            return True
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_end_msg", "message_id": callback.message.id}
        await callback.message.edit_text(
            "📥 **Set End Message**\n\nPlease send or forward the message you want to set as the **End Message**. It can be text, sticker, photo, video, etc.\n\n❌ Send /cancel to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="start_end_msg_menu")]])
        )
        return True

    elif data == "del_start_msg":
        await database.update_settings({"start_msg_db_id": None})
        await callback.answer("Start message has been reset.", show_alert=True)
        await show_start_end_msg_menu(client, callback.message.chat.id, callback.message.id)
        return True

    elif data == "del_end_msg":
        await database.update_settings({"end_msg_db_id": None})
        await callback.answer("End message has been reset.", show_alert=True)
        await show_start_end_msg_menu(client, callback.message.chat.id, callback.message.id)
        return True

    return False
