import json
from pyrogram import Client
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
import database
from main_helpers import (
    ADMIN_STATES, log_admin_action
)
from main_ui_config import (
    show_bot_config, show_fsub_menu, show_fsub_ch_details
)

async def handle_fsub_states(client: Client, message: Message, state: str, state_data: dict, message_id: int) -> bool:
    user_id = message.from_user.id

    # 1. Waiting for Welcome Message Template
    if state == "waiting_for_welcome":
        new_tpl = message.text
        await database.update_settings({"welcome_msg": new_tpl})
        ADMIN_STATES.pop(user_id, None)
        if message_id:
            await show_bot_config(client, message.chat.id, message_id)
        else:
            await message.reply_text("✅ Welcome message template updated!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Configurations", callback_data="bot_config")]]))
        return True

    # 2. Waiting for Force Subscribe Channel Input
    elif state == "waiting_for_fsub_channel":
        chat_id = None
        title = "Channel"
        username = ""
        if message.forward_origin:
            origin = message.forward_origin
            if hasattr(origin, "chat") and origin.chat:
                chat_id = origin.chat.id
                title = origin.chat.title or "Channel"
                username = origin.chat.username or ""
            elif hasattr(origin, "sender_chat") and origin.sender_chat:
                chat_id = origin.sender_chat.id
                title = origin.sender_chat.title or "Channel"
                username = origin.sender_chat.username or ""
        if not chat_id and message.forward_from_chat:
            chat_id = message.forward_from_chat.id
            title = message.forward_from_chat.title or "Channel"
            username = message.forward_from_chat.username or ""
        
        if not chat_id:
            input_val = message.text.strip() if message.text else ""
            if not input_val:
                if message_id:
                    await client.edit_message_text(chat_id=message.chat.id, message_id=message_id, text="⚠️ Invalid input. Please send a forwarded message or a channel ID/username.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="fsub_menu")]]))
                else:
                    await message.reply_text("⚠️ Invalid input.")
                return True
            if input_val.startswith("-100") or input_val.isdigit():
                chat_id = int(input_val)
            else:
                chat_id = input_val
            title = "Channel"
            username = input_val if input_val.startswith("@") else f"@{input_val}"

        invite_link = ""
        try:
            chat = await client.get_chat(chat_id)
            title = chat.title or title
            if chat.username:
                username = f"@{chat.username}"
                invite_link = f"https://t.me/{chat.username}"
            elif chat.invite_link:
                invite_link = chat.invite_link
            else:
                invite_link = await client.export_chat_invite_link(chat_id)
        except Exception as e:
            print(f"Failed to fetch details for channel {chat_id}: {e}")
        
        settings = await database.get_settings()
        raw_channels = settings.get("fsub_channels") or ""
        channels_list = []
        if raw_channels.startswith("["):
            try:
                channels_list = json.loads(raw_channels)
            except Exception:
                channels_list = []
        else:
            for c in raw_channels.split(","):
                c = c.strip()
                if c:
                    channels_list.append({"id": c, "title": "Channel", "invite_link": ""})
        
        already_exists = False
        for ch in channels_list:
            if str(ch.get("id")) == str(chat_id) or (username and ch.get("username") == username):
                already_exists = True
                break
        
        if already_exists:
            ADMIN_STATES.pop(user_id, None)
            if message_id:
                await show_fsub_menu(client, message.chat.id, message_id)
            else:
                await message.reply_text("❌ Channel already exists.")
            return True
        
        channels_list.append({
            "id": str(chat_id),
            "title": title,
            "username": username,
            "invite_link": invite_link
        })
        
        await database.update_settings({"fsub_channels": json.dumps(channels_list)})
        ADMIN_STATES.pop(user_id, None)
        if message_id:
            await show_fsub_menu(client, message.chat.id, message_id)
        else:
            await message.reply_text("✅ Channel added!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to FSub Menu", callback_data="fsub_menu")]]))
        return True

    # 3. Waiting for FSub Channel Invite Link Edit
    elif state == "waiting_for_fsub_edit_link":
        new_link = message.text.strip() if message.text else ""
        if not new_link.startswith("http://") and not new_link.startswith("https://"):
            return await message.reply_text("⚠️ Invalid URL. Please send a link starting with http:// or https://")
        
        idx = state_data["data"]["index"]
        settings = await database.get_settings()
        raw_channels = settings.get("fsub_channels") or ""
        channels_list = []
        try:
            channels_list = json.loads(raw_channels)
        except Exception:
            pass
        
        if 0 <= idx < len(channels_list):
            channels_list[idx]["invite_link"] = new_link
            await database.update_settings({"fsub_channels": json.dumps(channels_list)})
            ADMIN_STATES.pop(user_id, None)
            if message_id:
                await show_fsub_ch_details(client, message.chat.id, message_id, idx)
            else:
                await message.reply_text("✅ Invite link updated!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"fsub_ch_{idx}")]]))
        else:
            ADMIN_STATES.pop(user_id, None)
            if message_id:
                await show_fsub_menu(client, message.chat.id, message_id)
            else:
                await message.reply_text("❌ Invalid channel index.")
        return True

    return False
