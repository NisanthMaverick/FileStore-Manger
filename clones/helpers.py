import asyncio
import json
from pyrogram import Client
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from pyrogram.errors import UserNotParticipant, ChatAdminRequired, PeerIdInvalid
import database

# Active clone clients in-memory store
ACTIVE_CLONES = {}

# Dynamic welcome buttons generator for clone bots
def get_clone_welcome_markup(custom_buttons_str: str):
    buttons = []
    try:
        custom_buttons = json.loads(custom_buttons_str)
        row = []
        for b in custom_buttons:
            row.append(InlineKeyboardButton(b["text"], url=b["url"]))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
    except Exception as e:
        print(f"Error parsing custom buttons: {e}")
    return InlineKeyboardMarkup(buttons) if buttons else None

# Helper to check if user has subscribed to Force-Subscribe channels
async def check_user_subscribed(client: Client, user_id: int) -> tuple[bool, list[dict]]:
    settings = await database.get_settings()
    if not settings.get("fsub_enabled") or not settings.get("fsub_channels"):
        return True, []

    raw_channels = settings.get("fsub_channels") or ""
    channels_data = []
    if raw_channels.startswith("["):
        try:
            channels_data = json.loads(raw_channels)
        except Exception:
            channels_data = []
    
    if not channels_data:
        for c in raw_channels.split(","):
            c = c.strip()
            if c:
                channels_data.append({"id": c, "title": "Channel", "invite_link": ""})
    
    not_joined = []

    for ch in channels_data:
        channel_id = ch.get("id")
        try:
            chat_id = int(channel_id) if str(channel_id).startswith("-100") or str(channel_id).isdigit() else channel_id
            member = await client.get_chat_member(chat_id, user_id)
            if member.status == "kicked":
                not_joined.append({**ch, "banned": True})
        except UserNotParticipant:
            not_joined.append({**ch, "banned": False})
        except (PeerIdInvalid, ChatAdminRequired):
            print(f"Warning: Bot cannot check membership in {channel_id}. Lacks admin/access.")
            continue
        except Exception as e:
            print(f"FSub error checking {channel_id} for {user_id}: {e}")
            continue

    if not_joined:
        invite_buttons = []
        for item in not_joined:
            if item.get("banned"):
                continue
            
            link = item.get("invite_link")
            title = item.get("title") or "Channel"
            
            if not link:
                channel_ref = item["id"]
                try:
                    chat_id = int(channel_ref) if str(channel_ref).startswith("-100") or str(channel_ref).isdigit() else channel_ref
                    chat = await client.get_chat(chat_id)
                    if chat.username:
                        link = f"https://t.me/{chat.username}"
                    elif chat.invite_link:
                        link = chat.invite_link
                    else:
                        link = await client.export_chat_invite_link(chat_id)
                except Exception as e:
                    print(f"Failed to generate invite link for {channel_ref}: {e}")
                    if isinstance(channel_ref, str) and channel_ref.startswith("@"):
                        link = f"https://t.me/{channel_ref[1:]}"
            
            if link:
                invite_buttons.append({"text": f"Join {title} 📣", "url": link})
            else:
                invite_buttons.append({"text": f"Join {title} 📣", "url": "https://t.me"})
        
        return False, invite_buttons

    return True, []

# Helper to log download to Log Channel
async def log_download_action(client: Client, file_info: dict, user_message: Message):
    pass

async def log_new_user_start(client: Client, message: Message):
    try:
        settings = await database.get_settings()
        log_channel = settings.get("log_channel_id")
        if log_channel:
            user = message.from_user
            lang = (user.language_code or "EN").upper()
            bot_me = client.me
            
            text = (
                "👤 **NEW USER STARTED BOT** 👤\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 **User Name :** {user.first_name}\n"
                f"🆔 **User ID :** `{user.id}`\n"
                f"🔗 **Profile Link :** [Click Here](tg://user?id={user.id})\n"
                f"🌐 **Language :** {lang}\n"
                f"🤖 **Via Bot :** @{bot_me.username} ({bot_me.first_name})"
            )
            await client.send_message(
                chat_id=int(log_channel) if log_channel.startswith("-100") or log_channel.isdigit() else log_channel,
                text=text,
                disable_web_page_preview=True
            )
    except Exception as e:
        print(f"Failed to log new user start: {e}")

def get_readable_size(size_in_bytes: int) -> str:
    if not size_in_bytes:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_in_bytes < 1024:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024
    return f"{size_in_bytes:.2f} PB"

async def delete_messages_delayed(client: Client, chat_id: int, message_ids: list, delay_seconds: int):
    await asyncio.sleep(delay_seconds)
    try:
        await client.delete_messages(chat_id=chat_id, message_ids=message_ids)
    except Exception as e:
        print(f"Failed to auto-delete messages in chat {chat_id}: {e}")

async def handle_auto_delete_if_enabled(client: Client, chat_id: int, sent_message_ids: list):
    settings = await database.get_settings()
    if settings.get("auto_delete_enabled"):
        duration = settings.get("auto_delete_duration", 5)
        try:
            warning_msg = await client.send_message(
                chat_id=chat_id,
                text=f"⚠️ These files will be automatically deleted after {duration} minute(s)."
            )
            sent_message_ids.append(warning_msg.id)
        except Exception as e:
            print(f"Failed to send auto-delete warning: {e}")
        
        asyncio.create_task(delete_messages_delayed(client, chat_id, sent_message_ids, duration * 60))

async def copy_messages_with_start_end(client: Client, user_id: int, db_channel: str, file_msg_ids: list) -> list:
    settings = await database.get_settings()
    dest_chat = int(db_channel) if db_channel.startswith("-100") or db_channel.isdigit() else db_channel
    
    sent_ids = []
    
    # 1. Send Start Message if enabled
    if settings.get("start_end_msg_enabled") and settings.get("start_msg_db_id"):
        try:
            start_msg = await client.copy_message(
                chat_id=user_id,
                from_chat_id=dest_chat,
                message_id=settings["start_msg_db_id"]
            )
            sent_ids.append(start_msg.id)
        except Exception as e:
            print(f"Failed to send start message: {e}")
            
    # 2. Send the files
    user_delay = settings.get("user_send_delay", 3)
    for idx, msg_id in enumerate(file_msg_ids):
        if idx > 0 and user_delay > 0:
            await asyncio.sleep(user_delay)
        try:
            msg = await client.copy_message(
                chat_id=user_id,
                from_chat_id=dest_chat,
                message_id=msg_id
            )
            sent_ids.append(msg.id)
        except Exception as e:
            print(f"Failed to copy file message {msg_id}: {e}")
            
    # 3. Send End Message if enabled
    if settings.get("start_end_msg_enabled") and settings.get("end_msg_db_id"):
        try:
            end_msg = await client.copy_message(
                chat_id=user_id,
                from_chat_id=dest_chat,
                message_id=settings["end_msg_db_id"]
            )
            sent_ids.append(end_msg.id)
        except Exception as e:
            print(f"Failed to send end message: {e}")
            
    return sent_ids
