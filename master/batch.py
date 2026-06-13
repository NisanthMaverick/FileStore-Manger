import asyncio
import uuid
from pyrogram import Client
from pyrogram.types import Message
import database

async def copy_files_silently(client: Client, db_channel: str, source_chat_id: int, start_id: int, end_id: int, series_id: int, section_id: int, file_name_prefix: str = None):
    settings = await database.get_settings()
    db_delay = settings.get("db_upload_delay", 3)
    dest_chat = int(db_channel) if db_channel.startswith("-100") or db_channel.isdigit() else db_channel
    is_source_db = (source_chat_id == dest_chat)
    for idx, current_id in enumerate(range(start_id, end_id + 1)):
        if idx > 0 and db_delay > 0 and not is_source_db:
            await asyncio.sleep(db_delay)
        try:
            if is_source_db:
                copied_msg = await client.get_messages(chat_id=source_chat_id, message_ids=current_id)
                if not copied_msg or copied_msg.empty:
                    continue
            else:
                copied_msg = await client.copy_message(
                    chat_id=dest_chat,
                    from_chat_id=source_chat_id,
                    message_id=current_id
                )
            media = copied_msg.document or copied_msg.video or copied_msg.audio or copied_msg.photo or copied_msg.animation
            file_name = file_name_prefix or "Text Message"
            file_size = 0
            mime_type = "text/plain"
            caption = copied_msg.caption or copied_msg.text or ""
            
            if media:
                if not file_name_prefix:
                    file_name = getattr(media, "file_name", "Photo" if copied_msg.photo else "Media File")
                file_size = getattr(media, "file_size", 0)
                mime_type = getattr(media, "mime_type", "image/jpeg" if copied_msg.photo else "unknown")
            
            file_code = str(uuid.uuid4())[:8]
            await database.add_file(
                file_code=file_code,
                message_id=copied_msg.id,
                file_name=file_name,
                file_size=file_size,
                mime_type=mime_type,
                caption=caption,
                series_id=series_id,
                section_id=section_id
            )
        except Exception as e:
            print(f"Silent copy error on message {current_id} from {source_chat_id}: {e}")

async def run_batch_copy(client: Client, admin_chat_id: int, progress_message_id: int, source_chat_id: int, start_id: int, end_id: int, series_id: int, section_id: int, redirect_folder_id: int = None, clear_before: bool = True, custom_file_name: str = None):
    settings = await database.get_settings()
    db_channel = settings.get("db_channel_id")
    db_delay = settings.get("db_upload_delay", 3)
    if not db_channel:
        try:
            await client.edit_message_text(chat_id=admin_chat_id, message_id=progress_message_id, text="❌ DB Storage Channel is not configured. Batch copy cancelled.")
        except Exception:
            pass
        return

    # Clear old files only if requested (replace mode)
    if section_id and clear_before:
        await database.clear_section_files(section_id)

    dest_chat = int(db_channel) if db_channel.startswith("-100") or db_channel.isdigit() else db_channel
    
    dest_chat_id = dest_chat
    try:
        dest_chat_obj = await client.get_chat(dest_chat)
        dest_chat_id = dest_chat_obj.id
    except Exception:
        pass

    source_chat_id_resolved = source_chat_id
    try:
        source_chat_obj = await client.get_chat(source_chat_id)
        source_chat_id_resolved = source_chat_obj.id
    except Exception:
        pass

    is_source_db = (source_chat_id_resolved == dest_chat_id)
    total_messages = end_id - start_id + 1
    copied_count = 0
    skipped_count = 0

    from .ui_files import show_series_browse

    try:
        for idx, current_id in enumerate(range(start_id, end_id + 1)):
            if idx > 0 and db_delay > 0 and not is_source_db:
                await asyncio.sleep(db_delay)
            if (copied_count + skipped_count) % 5 == 0 or (copied_count + skipped_count) == total_messages:
                try:
                    action_word = "Linking" if is_source_db else "Copying"
                    await client.edit_message_text(
                        chat_id=admin_chat_id,
                        message_id=progress_message_id,
                        text=f"⏳ **{action_word} messages...**\nProgress: `{copied_count + skipped_count}/{total_messages}`\nProcessed: `{copied_count}` | Skipped: `{skipped_count}`"
                    )
                except Exception:
                    pass
                await asyncio.sleep(0.5)

            try:
                if is_source_db:
                    copied_msg = await client.get_messages(chat_id=source_chat_id, message_ids=current_id)
                    if not copied_msg or copied_msg.empty:
                        skipped_count += 1
                        continue
                else:
                    copied_msg = await client.copy_message(
                        chat_id=dest_chat,
                        from_chat_id=source_chat_id,
                        message_id=current_id
                    )
                
                media = copied_msg.document or copied_msg.video or copied_msg.audio or copied_msg.photo or copied_msg.animation
                file_name = custom_file_name or "Text Message"
                file_size = 0
                mime_type = "text/plain"
                caption = copied_msg.caption or copied_msg.text or ""
                
                if media:
                    if not custom_file_name:
                        file_name = getattr(media, "file_name", "Photo" if copied_msg.photo else "Media File")
                    file_size = getattr(media, "file_size", 0)
                    mime_type = getattr(media, "mime_type", "image/jpeg" if copied_msg.photo else "unknown")
                
                file_code = str(uuid.uuid4())[:8]
                
                await database.add_file(
                    file_code=file_code,
                    message_id=copied_msg.id,
                    file_name=file_name,
                    file_size=file_size,
                    mime_type=mime_type,
                    caption=caption,
                    series_id=series_id,
                    section_id=section_id
                )
                copied_count += 1
                
            except Exception as e:
                print(f"Skipped copy/link of message {current_id} from {source_chat_id}: {e}")
                skipped_count += 1
                
        action_title = "linking" if is_source_db else "copy"
        await client.edit_message_text(
            chat_id=admin_chat_id,
            message_id=progress_message_id,
            text=f"✅ **Batch {action_title} completed successfully!**\n\nTotal messages: `{total_messages}`\nProcessed: `{copied_count}`\nSkipped: `{skipped_count}`"
        )
        
        await asyncio.sleep(1)
        await show_series_browse(client, admin_chat_id, progress_message_id, series_id, redirect_folder_id if redirect_folder_id and redirect_folder_id > 0 else None)
        
    except Exception as outer_err:
        print(f"Error in batch copy task: {outer_err}")
        try:
            await client.edit_message_text(
                chat_id=admin_chat_id,
                message_id=progress_message_id,
                text=f"❌ **Error during batch copy:** {outer_err}"
            )
        except Exception:
            pass

async def run_multi_range_copy(
    client: Client,
    admin_chat_id: int,
    progress_message_id: int,
    ranges: list,
    series_id: int,
    section_id: int,
    redirect_folder_id: int = None,
    clear_before: bool = True,
    custom_file_name: str = None,
    library_skip: int = 0
):
    settings = await database.get_settings()
    db_channel = settings.get("db_channel_id")
    db_delay = settings.get("db_upload_delay", 3)
    if not db_channel:
        try:
            await client.edit_message_text(chat_id=admin_chat_id, message_id=progress_message_id, text="❌ DB Storage Channel is not configured. Copy cancelled.")
        except Exception:
            pass
        return

    # Clear old files only if requested (replace mode)
    if section_id and clear_before:
        await database.clear_section_files(section_id)

    dest_chat = int(db_channel) if db_channel.startswith("-100") or db_channel.isdigit() else db_channel
    dest_chat_id = dest_chat
    try:
        dest_chat_obj = await client.get_chat(dest_chat)
        dest_chat_id = dest_chat_obj.id
    except Exception:
        pass
    
    # Calculate total messages across all ranges
    total_messages = 0
    for r in ranges:
        total_messages += (r["end_id"] - r["start_id"] + 1)
        
    copied_count = 0
    skipped_count = 0

    from .ui_files import show_series_browse

    try:
        idx_global = 0
        for r in ranges:
            source_chat_id = r["chat_id"]
            start_id = r["start_id"]
            end_id = r["end_id"]
            
            source_chat_id_resolved = source_chat_id
            try:
                source_chat_obj = await client.get_chat(source_chat_id)
                source_chat_id_resolved = source_chat_obj.id
            except Exception:
                pass
                
            is_source_db = (source_chat_id_resolved == dest_chat_id)
            
            for current_id in range(start_id, end_id + 1):
                if idx_global > 0 and db_delay > 0 and not is_source_db:
                    await asyncio.sleep(db_delay)
                
                if (copied_count + skipped_count) % 5 == 0 or (copied_count + skipped_count) == total_messages:
                    try:
                        action_word = "Linking" if is_source_db else "Copying"
                        await client.edit_message_text(
                            chat_id=admin_chat_id,
                            message_id=progress_message_id,
                            text=f"⏳ **{action_word} messages...**\nProgress: `{copied_count + skipped_count}/{total_messages}`\nProcessed: `{copied_count}` | Skipped: `{skipped_count}`"
                        )
                    except Exception:
                        pass
                    await asyncio.sleep(0.5)

                try:
                    if is_source_db:
                        copied_msg = await client.get_messages(chat_id=source_chat_id, message_ids=current_id)
                        if not copied_msg or copied_msg.empty:
                            skipped_count += 1
                            idx_global += 1
                            continue
                    else:
                        copied_msg = await client.copy_message(
                            chat_id=dest_chat,
                            from_chat_id=source_chat_id,
                            message_id=current_id
                        )
                    
                    media = copied_msg.document or copied_msg.video or copied_msg.audio or copied_msg.photo or copied_msg.animation
                    file_name = custom_file_name or "Text Message"
                    file_size = 0
                    mime_type = "text/plain"
                    caption = copied_msg.caption or copied_msg.text or ""
                    
                    if media:
                        if not custom_file_name:
                            file_name = getattr(media, "file_name", "Photo" if copied_msg.photo else "Media File")
                        file_size = getattr(media, "file_size", 0)
                        mime_type = getattr(media, "mime_type", "image/jpeg" if copied_msg.photo else "unknown")
                    
                    file_code = str(uuid.uuid4())[:8]
                    
                    await database.add_file(
                        file_code=file_code,
                        message_id=copied_msg.id,
                        file_name=file_name,
                        file_size=file_size,
                        mime_type=mime_type,
                        caption=caption,
                        series_id=series_id,
                        section_id=section_id
                    )
                    copied_count += 1
                    
                except Exception as e:
                    print(f"Skipped copy/link of message {current_id} from {source_chat_id}: {e}")
                    skipped_count += 1
                
                idx_global += 1

        action_title = "linking" if all((r["chat_id"] == dest_chat) for r in ranges) else "copy"
        await client.edit_message_text(
            chat_id=admin_chat_id,
            message_id=progress_message_id,
            text=f"✅ **Batch {action_title} completed successfully!**\n\nTotal messages: `{total_messages}`\nProcessed: `{copied_count}`\nSkipped: `{skipped_count}`"
        )
        
        await asyncio.sleep(1)
        await show_series_browse(
            client,
            admin_chat_id,
            progress_message_id,
            series_id,
            redirect_folder_id if redirect_folder_id and redirect_folder_id > 0 else None,
            library_skip=library_skip
        )
        
    except Exception as outer_err:
        print(f"Error in batch copy task: {outer_err}")
        try:
            await client.edit_message_text(
                chat_id=admin_chat_id,
                message_id=progress_message_id,
                text=f"❌ **Error during batch copy:** {outer_err}"
            )
        except Exception:
            pass

