from pyrogram import Client
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import database
from .helpers import get_back_button

async def show_folder_management(client: Client, chat_id: int, message_id: int, series_id: int, section_id: int = 0):
    series = await database.get_series(series_id)
    if not series:
        try:
            await client.edit_message_text(chat_id=chat_id, message_id=message_id, text="❌ Series not found.", reply_markup=InlineKeyboardMarkup([get_back_button("manage_series")]))
        except Exception:
            pass
        return

    is_root = (section_id == 0)
    current_sec = None
    if not is_root:
        current_sec = await database.get_section(section_id)
        if not current_sec:
            try:
                await client.edit_message_text(chat_id=chat_id, message_id=message_id, text="❌ Folder not found.", reply_markup=InlineKeyboardMarkup([InlineKeyboardButton("🔙 Back to Series", callback_data=f"browse_sec_{series_id}_0")]))
            except Exception:
                pass
            return

    if is_root:
        name = series["title"]
        custom_msg = series.get("custom_msg")
        buttons_per_row = series.get("buttons_per_row", 2)
        type_str = "Series (Root)"
    else:
        name = current_sec["name"]
        custom_msg = current_sec.get("custom_msg")
        buttons_per_row = current_sec.get("buttons_per_row", 2)
        type_str = "Folder"

    custom_msg_status = custom_msg if custom_msg else "Default (Breadcrumbs / Description)"
    
    text = (
        f"⚙️ **{type_str} Settings: {name}**\n\n"
        f"💬 **Custom Message:**\n`{custom_msg_status}`\n\n"
        f"🔢 **Buttons per Row:** `{buttons_per_row}`\n\n"
        "Configure folder settings or perform administrative actions below:"
    )

    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💬 Edit Message", callback_data=f"edit_sec_msg_{series_id}_{section_id}"),
            InlineKeyboardButton("🔢 Buttons Per Row", callback_data=f"edit_sec_cols_{series_id}_{section_id}")
        ],
        [
            InlineKeyboardButton("✏️ Rename", callback_data=f"rename_series_opt_{series_id}" if is_root else f"rename_sec_{series_id}_{section_id}"),
            InlineKeyboardButton("🗑 Delete", callback_data=f"tree_del_series_{series_id}" if is_root else f"tree_del_sec_{series_id}_{section_id}")
        ],
        [
            InlineKeyboardButton("🔙 Back to Folder", callback_data=f"browse_sec_{series_id}_{section_id}")
        ]
    ])

    try:
        await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup)
    except Exception as e:
        print(f"Error rendering folder_management: {e}")

async def show_series_browse(client: Client, chat_id: int, message_id: int, series_id: int, section_id: int = None):
    series = await database.get_series(series_id)
    if not series:
        try:
            await client.edit_message_text(chat_id=chat_id, message_id=message_id, text="Series not found.", reply_markup=InlineKeyboardMarkup([get_back_button("manage_series")]))
        except Exception:
            pass
        return

    current_sec = None
    if section_id:
        current_sec = await database.get_section(section_id)

    sections = await database.list_sections(series_id, parent_id=section_id)

    path_str = f"🎬 **Series:** {series['title']}"
    if section_id:
        sec_path = await database.get_section_path(section_id)
        path_str += f" › {sec_path}"

    text = f"{path_str}\n"
    if series['description'] and not section_id:
        text += f"_{series['description']}_\n"
    text += "\n"

    per_row = 2
    if section_id:
        if current_sec:
            per_row = current_sec.get("buttons_per_row", 2)
    else:
        per_row = series.get("buttons_per_row", 2)

    buttons = []

    if sections:
        row = []
        for s in sections:
            if s.get("sec_type") == "files":
                btn = InlineKeyboardButton(f"📥 {s['name']}", callback_data=f"filesec_act_{series_id}_{s['id']}")
            else:
                btn = InlineKeyboardButton(f"📁 {s['name']}", callback_data=f"browse_sec_{series_id}_{s['id']}")
            row.append(btn)
            if len(row) == per_row:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
    else:
        text += "_This folder is empty._\n"

    buttons.append([
        InlineKeyboardButton("➕ Add Button", callback_data=f"tree_add_btn_{series_id}_{section_id or 0}"),
        InlineKeyboardButton("📦 Bulk Add", callback_data=f"tree_bulk_add_{series_id}_{section_id or 0}")
    ])
    
    if section_id:
        buttons.append([
            InlineKeyboardButton("⚙️ Folder Management", callback_data=f"manage_folder_opt_{series_id}_{section_id}")
        ])
    else:
        buttons.append([
            InlineKeyboardButton("⚙️ Series Management", callback_data=f"manage_folder_opt_{series_id}_0")
        ])

    if section_id:
        parent_id = current_sec["parent_id"] if current_sec else None
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"browse_sec_{series_id}_{parent_id or 0}")])
    else:
        buttons.append([InlineKeyboardButton("🔙 Back to Series Library", callback_data="manage_series")])

    try:
        await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        print(f"Error rendering show_series_browse: {e}")

async def show_manage_series(client: Client, chat_id: int, message_id: int):
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
    try:
        await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        print(f"Error rendering manage_series: {e}")

async def show_manage_files(client: Client, chat_id: int, message_id: int):
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📤 Store New File", callback_data="add_file"),
            InlineKeyboardButton("📁 Browse Files", callback_data="list_files_0")
        ],
        [
            InlineKeyboardButton("🎬 Series Library", callback_data="manage_series"),
            InlineKeyboardButton("➕ Create Series", callback_data="create_series")
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="main_panel")
        ]
    ])
    try:
        await client.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="📂 **File and Series Management**\n\nHere you can add new media files, view stored files, and create/manage video/episodes series.",
            reply_markup=markup
        )
    except Exception as e:
        print(f"Error rendering manage_files: {e}")

async def show_filesec_actions(client: Client, chat_id: int, message_id: int, series_id: int, section_id: int, sec: dict, total_files: int):
    parent_id = sec["parent_id"]
    text = f"📥 **{sec['name']}**\n\n📂 Contains **{total_files} file(s)**\n\nChoose an action:"
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add More Files", callback_data=f"filesec_add_{series_id}_{section_id}"),
            InlineKeyboardButton("🔄 Replace All Files", callback_data=f"filesec_replace_{series_id}_{section_id}")
        ],
        [
            InlineKeyboardButton("✏️ Rename Button", callback_data=f"rename_sec_{series_id}_{section_id}"),
            InlineKeyboardButton("🗑 Delete Button", callback_data=f"tree_del_sec_{series_id}_{section_id}")
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data=f"browse_sec_{series_id}_{parent_id or 0}")
        ]
    ])
    try:
        await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup)
    except Exception as e:
        print(f"Error rendering filesec_actions: {e}")
