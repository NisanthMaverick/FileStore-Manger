import json
from pyrogram import Client
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import database
from .helpers import get_back_button

async def show_bot_config(client: Client, chat_id: int, message_id: int):
    settings = await database.get_settings()
    fsub_status = "Enabled ✅" if settings.get("fsub_enabled") else "Disabled ❌"
    raw_channels = settings.get("fsub_channels") or ""
    channels_count = 0
    if raw_channels.startswith("["):
        try:
            channels_count = len(json.loads(raw_channels))
        except Exception:
            pass
    elif raw_channels.strip():
        channels_count = len(raw_channels.split(","))

    auto_del_status = "Enabled ✅" if settings.get("auto_delete_enabled") else "Disabled ❌"
    auto_del_dur = settings.get("auto_delete_duration", 5)

    start_end_status = "Enabled ✅" if settings.get("start_end_msg_enabled") else "Disabled ❌"
    start_set = "Configured" if settings.get("start_msg_db_id") else "Not Set ❌"
    end_set = "Configured" if settings.get("end_msg_db_id") else "Not Set ❌"

    user_send_delay = settings.get("user_send_delay", 3)
    protect_content_status = "Enabled ✅" if settings.get("protect_content_enabled") else "Disabled ❌"
    text = f"⚙️ **Bot Configurations**\n\n" \
           f"📝 **Welcome Message Template:**\n" \
           f"`{settings.get('welcome_msg')}`\n\n" \
           f"🔗 **Force-Subscribe Settings:**\n" \
           f"▪️ Status: {fsub_status}\n" \
           f"▪️ Channels: `{channels_count}` configured\n\n" \
           f"⏱ **File Auto Delete Timer:**\n" \
           f"▪️ Status: {auto_del_status}\n" \
           f"▪️ Duration: `{auto_del_dur}` minute(s)\n\n" \
           f"💬 **Start & End Messages:**\n" \
           f"▪️ Status: {start_end_status}\n" \
           f"▪️ Start Message: {start_set}\n" \
           f"▪️ End Message: {end_set}\n\n" \
           f"⏱ **User File Send Delay:** `{user_send_delay}` second(s)\n\n" \
           f"🔒 **Forward Restriction (Protect Content):** `{protect_content_status}`\n\n" \
           f"🔘 **Custom Buttons:**\n"
    
    buttons_list = json.loads(settings.get("custom_buttons", "[]"))
    if not buttons_list:
        text += "_No custom buttons added._"
    else:
        for b in buttons_list:
            text += f"▪️ {b['text']} -> {b['url']}\n"
    
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📝 Customize Welcome Msg", callback_data="edit_welcome"),
            InlineKeyboardButton("📢 Force Subscribe (FSub)", callback_data="fsub_menu")
        ],
        [
            InlineKeyboardButton("🔘 Custom Buttons Manager", callback_data="btn_mgr"),
            InlineKeyboardButton("⏱ File Auto Delete Timer", callback_data="auto_delete_menu")
        ],
        [
            InlineKeyboardButton("💬 Start & End Messages", callback_data="start_end_msg_menu"),
            InlineKeyboardButton("⏱ User Send Delay", callback_data="edit_user_send_delay")
        ],
        [
            InlineKeyboardButton("🔒 Forward Restricted", callback_data="toggle_protect_content")
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="main_panel")
        ]
    ])
    try:
        await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup)
    except Exception as e:
        print(f"Error rendering bot_config: {e}")

async def show_auto_delete_menu(client: Client, chat_id: int, message_id: int):
    settings = await database.get_settings()
    enabled = settings.get("auto_delete_enabled", False)
    duration = settings.get("auto_delete_duration", 5)

    status_str = "Enabled ✅" if enabled else "Disabled ❌"
    text = (
        "⏱ **File Auto Delete Timer Settings**\n\n"
        f"⚡ **Auto Delete Status:** {status_str}\n"
        f"⏳ **Delete Duration:** `{duration}` minute(s)\n\n"
        "Configure automatic deletion of files sent to users below:"
    )

    toggle_btn_text = "🔴 Disable Auto Delete" if enabled else "🟢 Enable Auto Delete"
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(toggle_btn_text, callback_data="toggle_auto_delete"),
            InlineKeyboardButton("⏳ Edit Duration", callback_data="edit_auto_delete_duration")
        ],
        [
            InlineKeyboardButton("🔙 Back to Bot Config", callback_data="bot_config")
        ]
    ])
    try:
        await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup)
    except Exception as e:
        print(f"Error rendering auto_delete_menu: {e}")

async def show_fsub_menu(client: Client, chat_id: int, message_id: int):
    settings = await database.get_settings()
    fsub_status = "Enabled ✅" if settings.get("fsub_enabled") else "Disabled ❌"
    
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
                channels_list.append({"id": c, "title": c, "invite_link": ""})
    
    text = f"📢 **Force Subscribe (FSub) Settings**\n\n" \
           f"Force Subscribe requires users to join your channels before they can download files from the bot.\n\n" \
           f"⚡ **FSub Status:** {fsub_status}\n" \
           f"📣 **Configured Channels:** {len(channels_list)}\n\n" \
           f"Select a channel below to view details/edit, or add a new channel:"
    
    buttons = []
    status_toggle_btn = "🔴 Disable FSub" if settings.get("fsub_enabled") else "🟢 Enable FSub"
    buttons.append([
        InlineKeyboardButton(status_toggle_btn, callback_data="toggle_fsub"),
        InlineKeyboardButton("➕ Add Channel", callback_data="add_fsub_channel")
    ])
    
    row = []
    for idx, ch in enumerate(channels_list):
        title = ch.get("title") or ch.get("id") or f"Channel {idx+1}"
        row.append(InlineKeyboardButton(f"📣 {title}", callback_data=f"fsub_ch_{idx}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="bot_config")])
    try:
        await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        print(f"Error rendering fsub_menu: {e}")

async def show_fsub_ch_details(client: Client, chat_id: int, message_id: int, idx: int):
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
                channels_list.append({"id": c, "title": c, "invite_link": ""})
    
    if idx < 0 or idx >= len(channels_list):
        await show_fsub_menu(client, chat_id, message_id)
        return
    
    ch = channels_list[idx]
    
    text = f"📣 **FSub Channel Configuration**\n\n" \
           f"▪️ **Title:** {ch.get('title')}\n" \
           f"▪️ **ID:** `{ch.get('id')}`\n" \
           f"▪️ **Username:** {ch.get('username') or '_None_'}\n" \
           f"▪️ **Invite Link:** {ch.get('invite_link') or '_None_'}\n\n" \
           f"Manage this channel using the options below:"
    
    buttons = [
        [
            InlineKeyboardButton("✏️ Edit Invite Link", callback_data=f"fsub_edit_link_{idx}"),
            InlineKeyboardButton("🗑 Delete Channel", callback_data=f"fsub_del_ch_{idx}")
        ],
        [
            InlineKeyboardButton("🔙 Back to Channels", callback_data="fsub_menu")
        ]
    ]
    try:
        await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        print(f"Error rendering fsub_ch_details: {e}")

async def show_btn_mgr(client: Client, chat_id: int, message_id: int):
    settings = await database.get_settings()
    buttons_list = json.loads(settings.get("custom_buttons", "[]"))
    
    text = "🔘 **Custom Buttons Manager**\n\nConfigure custom inline navigation buttons that appear on the welcome message.\n\nSelect a button below to edit or delete it:"
    
    markup_buttons = []
    row = []
    for idx, b in enumerate(buttons_list):
        row.append(InlineKeyboardButton(f"🔘 {b['text']}", callback_data=f"btn_details_{idx}"))
        if len(row) == 2:
            markup_buttons.append(row)
            row = []
    if row:
        markup_buttons.append(row)
    
    markup_buttons.append([InlineKeyboardButton("➕ Add Custom Button", callback_data="add_btn")])
    markup_buttons.append(get_back_button("bot_config"))
    
    try:
        await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=InlineKeyboardMarkup(markup_buttons))
    except Exception as e:
        print(f"Error rendering btn_mgr: {e}")

async def show_btn_details(client: Client, chat_id: int, message_id: int, idx: int):
    settings = await database.get_settings()
    buttons_list = json.loads(settings.get("custom_buttons", "[]"))
    
    if idx < 0 or idx >= len(buttons_list):
        await show_btn_mgr(client, chat_id, message_id)
        return
    
    btn = buttons_list[idx]
    
    text = f"🔘 **Custom Button Details**\n\n" \
           f"▪️ **Name:** {btn['text']}\n" \
           f"▪️ **URL / Link:** {btn['url']}\n\n" \
           f"Configure this button using the options below:"
    
    buttons = [
        [
            InlineKeyboardButton("✏️ Edit Link", callback_data=f"btn_edit_link_{idx}"),
            InlineKeyboardButton("🗑 Delete Button", callback_data=f"btn_delete_{idx}")
        ],
        [
            InlineKeyboardButton("🔙 Back to Buttons", callback_data="btn_mgr")
        ]
    ]
    try:
        await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        print(f"Error rendering btn_details: {e}")

async def show_start_end_msg_menu(client: Client, chat_id: int, message_id: int):
    settings = await database.get_settings()
    enabled = settings.get("start_end_msg_enabled", False)
    start_id = settings.get("start_msg_db_id")
    end_id = settings.get("end_msg_db_id")

    status_str = "Enabled ✅" if enabled else "Disabled ❌"
    start_str = f"Set (ID: `{start_id}`)" if start_id else "Not Configured ❌"
    end_str = f"Set (ID: `{end_id}`)" if end_id else "Not Configured ❌"

    text = (
        "💬 **Start & End Messages Settings**\n\n"
        f"⚡ **Status:** {status_str}\n"
        f"📤 **Start Message:** {start_str}\n"
        f"📥 **End Message:** {end_str}\n\n"
        "Configured messages will be sent to the user before and after the requested files are delivered."
    )

    toggle_btn_text = "🔴 Disable Messages" if enabled else "🟢 Enable Messages"
    
    buttons = [
        [
            InlineKeyboardButton(toggle_btn_text, callback_data="toggle_start_end_msg")
        ],
        [
            InlineKeyboardButton("📤 Set Start Message", callback_data="set_start_msg"),
            InlineKeyboardButton("📥 Set End Message", callback_data="set_end_msg")
        ],
        [
            InlineKeyboardButton("🗑 Reset Start Message", callback_data="del_start_msg"),
            InlineKeyboardButton("🗑 Reset End Message", callback_data="del_end_msg")
        ],
        [
            InlineKeyboardButton("🔙 Back to Bot Config", callback_data="bot_config")
        ]
    ]
    try:
        await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        print(f"Error rendering start_end_msg_menu: {e}")
