import json
from pyrogram import Client
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from pyrogram.errors import MessageNotModified
import database

# In-memory states for administrators
# Format: {user_id: {"state": "state_name", "data": dict}}
ADMIN_STATES = {}

# Keep reference to the Main Bot Client
main_bot_client = None

# Helper to send admin logs
async def log_admin_action(text: str):
    try:
        settings = await database.get_settings()
        log_channel = settings.get("log_channel_id")
        if log_channel and main_bot_client:
            await main_bot_client.send_message(
                chat_id=int(log_channel) if log_channel.startswith("-100") or log_channel.isdigit() else log_channel,
                text=text
            )
    except Exception as e:
        print(f"Failed to log admin action: {e}")

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

# Formatting helper for file size
def get_readable_size(size_in_bytes: int) -> str:
    if not size_in_bytes:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_in_bytes < 1024:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024
    return f"{size_in_bytes:.2f} PB"

# Safe message edit helper to avoid MessageNotModified exceptions
async def safe_edit_message(message: Message, text: str, reply_markup=None, disable_web_page_preview=False):
    try:
        await message.edit_text(text, reply_markup=reply_markup, disable_web_page_preview=disable_web_page_preview)
    except Exception as e:
        if "MESSAGE_NOT_MODIFIED" not in str(e).upper():
            print(f"Error editing message: {e}")

# Dynamic Redirect Button for Normal Users
async def get_welcome_markup():
    settings = await database.get_settings()
    primary = settings.get("primary_clone_username")
    buttons = []
    if primary:
        buttons.append([InlineKeyboardButton("Go to Bot 🤖", url=f"https://t.me/{primary}")])
    return InlineKeyboardMarkup(buttons) if buttons else None

# Admin Keyboards
def get_main_panel_markup():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📂 Storage & File Hub", callback_data="manage_files"),
            InlineKeyboardButton("👥 User & Subscribers", callback_data="sub_mgr")
        ],
        [
            InlineKeyboardButton("⚙️ Control & Bot Config", callback_data="bot_config"),
            InlineKeyboardButton("🔄 Database & Sync Engine", callback_data="db_sync")
        ],
        [
            InlineKeyboardButton("🛡️ Security & Admins", callback_data="admin_settings"),
            InlineKeyboardButton("❌ Terminate Session", callback_data="close_panel")
        ]
    ])

def get_back_button(target="main_panel"):
    return [InlineKeyboardButton("🔙 Back", callback_data=target)]

def parse_tg_link(link: str):
    link = link.replace("https://t.me/", "").replace("t.me/", "")
    parts = link.split("/")
    if len(parts) < 2:
        return None
    chat_username = parts[0]
    try:
        msg_id = int(parts[1])
        return chat_username, msg_id
    except ValueError:
        return None

def extract_msg_from_forward(message: Message):
    if message.forward_from_chat:
        return message.forward_from_chat.id, message.forward_from_message_id
    return None
