import asyncio
from .models import SessionLocal, Series, SeriesSection, FileRecord

def _add_file_sync(file_code: str, message_id: int, file_name: str, file_size: int, mime_type: str, caption: str, series_id=None, episode_number=None, section_id=None):
    with SessionLocal() as session:
        record = session.query(FileRecord).filter(FileRecord.file_code == file_code).first()
        if record:
            record.message_id = message_id
            record.file_name = file_name
            record.file_size = file_size
            record.mime_type = mime_type
            record.caption = caption
            record.series_id = series_id
            record.episode_number = episode_number
            record.section_id = section_id
        else:
            record = FileRecord(
                file_code=file_code,
                message_id=message_id,
                file_name=file_name,
                file_size=file_size,
                mime_type=mime_type,
                caption=caption,
                series_id=series_id,
                episode_number=episode_number,
                section_id=section_id
            )
            session.add(record)
        session.commit()

def _get_file_sync(file_code: str):
    with SessionLocal() as session:
        f = session.query(FileRecord).filter(FileRecord.file_code == file_code).first()
        if f:
            return {
                "file_code": f.file_code,
                "message_id": f.message_id,
                "file_name": f.file_name,
                "file_size": f.file_size,
                "mime_type": f.mime_type,
                "caption": f.caption,
                "series_id": f.series_id,
                "episode_number": f.episode_number,
                "section_id": f.section_id
            }
        return None

def _delete_file_sync(file_code: str) -> bool:
    with SessionLocal() as session:
        f = session.query(FileRecord).filter(FileRecord.file_code == file_code).first()
        if f:
            session.delete(f)
            session.commit()
            return True
        return False

def _list_files_sync(skip=0, limit=20, search=None, series_id=None, section_id=None, filter_root=False):
    with SessionLocal() as session:
        query = session.query(FileRecord)
        if section_id is not None:
            query = query.filter(FileRecord.section_id == section_id)
        elif series_id is not None:
            query = query.filter(FileRecord.series_id == series_id)
            if filter_root:
                query = query.filter(FileRecord.section_id == None)
        if search:
            query = query.filter(FileRecord.file_name.ilike(f"%{search}%"))
        total = query.count()
        records = query.order_by(FileRecord.message_id).offset(skip).limit(limit).all()
        files = [{
            "file_code": r.file_code,
            "message_id": r.message_id,
            "file_name": r.file_name,
            "file_size": r.file_size,
            "mime_type": r.mime_type,
            "caption": r.caption,
            "series_id": r.series_id,
            "episode_number": r.episode_number,
            "section_id": r.section_id
        } for r in records]
        return files, total

def _create_series_sync(title: str, description: str):
    with SessionLocal() as session:
        s = Series(title=title, description=description)
        session.add(s)
        session.commit()
        session.refresh(s)
        return s.id

def _get_series_sync(series_id: int):
    with SessionLocal() as session:
        s = session.query(Series).filter(Series.id == series_id).first()
        if s:
            return {
                "id": s.id,
                "title": s.title,
                "description": s.description,
                "custom_msg": s.custom_msg,
                "buttons_per_row": s.buttons_per_row,
                "display_order": s.display_order
            }
        return None

def _list_series_sync():
    with SessionLocal() as session:
        series_list = session.query(Series).order_by(Series.display_order.asc(), Series.title.asc()).all()
        return [{
            "id": s.id,
            "title": s.title,
            "description": s.description,
            "custom_msg": s.custom_msg,
            "buttons_per_row": s.buttons_per_row,
            "display_order": s.display_order
        } for s in series_list]

def _delete_series_sync(series_id: int):
    with SessionLocal() as session:
        s = session.query(Series).filter(Series.id == series_id).first()
        if s:
            session.delete(s)
            session.commit()
            return True
        return False

def _create_section_sync(name: str, series_id: int, parent_id: int = None, sec_type: str = "folder") -> int:
    with SessionLocal() as session:
        sec = SeriesSection(name=name, series_id=series_id, parent_id=parent_id, sec_type=sec_type)
        session.add(sec)
        session.commit()
        session.refresh(sec)
        return sec.id

def _get_section_sync(section_id: int):
    with SessionLocal() as session:
        sec = session.query(SeriesSection).filter(SeriesSection.id == section_id).first()
        if sec:
            return {
                "id": sec.id,
                "name": sec.name,
                "series_id": sec.series_id,
                "parent_id": sec.parent_id,
                "sec_type": sec.sec_type,
                "custom_msg": sec.custom_msg,
                "buttons_per_row": sec.buttons_per_row
            }
        return None

def _list_sections_sync(series_id: int, parent_id: int = None):
    with SessionLocal() as session:
        query = session.query(SeriesSection).filter(SeriesSection.series_id == series_id)
        if parent_id is None:
            query = query.filter(SeriesSection.parent_id == None)
        else:
            query = query.filter(SeriesSection.parent_id == parent_id)
        sections = query.order_by(SeriesSection.id).all()
        return [{
            "id": s.id,
            "name": s.name,
            "series_id": s.series_id,
            "parent_id": s.parent_id,
            "sec_type": s.sec_type,
            "custom_msg": s.custom_msg,
            "buttons_per_row": s.buttons_per_row
        } for s in sections]

def _delete_section_sync(section_id: int) -> bool:
    with SessionLocal() as session:
        sec = session.query(SeriesSection).filter(SeriesSection.id == section_id).first()
        if sec:
            session.delete(sec)
            session.commit()
            return True
        return False

def _get_section_path_sync(section_id: int) -> str:
    path_parts = []
    curr_id = section_id
    with SessionLocal() as session:
        while curr_id:
            sec = session.query(SeriesSection).filter(SeriesSection.id == curr_id).first()
            if not sec:
                break
            path_parts.append(sec.name)
            curr_id = sec.parent_id
    return " > ".join(reversed(path_parts))

def _update_section_sync(section_id: int, name: str) -> bool:
    with SessionLocal() as session:
        sec = session.query(SeriesSection).filter(SeriesSection.id == section_id).first()
        if sec:
            sec.name = name
            session.commit()
            return True
        return False

def _clear_section_files_sync(section_id: int):
    with SessionLocal() as session:
        session.query(FileRecord).filter(FileRecord.section_id == section_id).delete()
        session.commit()

def _update_series_settings_sync(series_id: int, custom_msg=None, buttons_per_row=None, title=None, description=None, display_order=None) -> bool:
    with SessionLocal() as session:
        s = session.query(Series).filter(Series.id == series_id).first()
        if s:
            if custom_msg is not None:
                s.custom_msg = None if custom_msg == "none" else custom_msg
            if buttons_per_row is not None:
                s.buttons_per_row = buttons_per_row
            if title is not None:
                s.title = title
            if description is not None:
                s.description = description
            if display_order is not None:
                s.display_order = display_order
            session.commit()
            return True
        return False

def _update_section_settings_sync(section_id: int, custom_msg, buttons_per_row) -> bool:
    with SessionLocal() as session:
        sec = session.query(SeriesSection).filter(SeriesSection.id == section_id).first()
        if sec:
            if custom_msg is not None:
                sec.custom_msg = None if custom_msg == "none" else custom_msg
            if buttons_per_row is not None:
                sec.buttons_per_row = buttons_per_row
            session.commit()
            return True
        return False

# --- Async wrappers ---
async def create_series(title: str, description: str):
    return await asyncio.to_thread(_create_series_sync, title, description)

async def get_series(series_id: int):
    return await asyncio.to_thread(_get_series_sync, series_id)

async def list_series():
    return await asyncio.to_thread(_list_series_sync)

async def delete_series(series_id: int):
    return await asyncio.to_thread(_delete_series_sync, series_id)

async def create_section(name: str, series_id: int, parent_id: int = None, sec_type: str = "folder") -> int:
    return await asyncio.to_thread(_create_section_sync, name, series_id, parent_id, sec_type)

async def get_section(section_id: int):
    return await asyncio.to_thread(_get_section_sync, section_id)

async def list_sections(series_id: int, parent_id: int = None):
    return await asyncio.to_thread(_list_sections_sync, series_id, parent_id)

async def delete_section(section_id: int):
    return await asyncio.to_thread(_delete_section_sync, section_id)

async def get_section_path(section_id: int) -> str:
    return await asyncio.to_thread(_get_section_path_sync, section_id)

async def update_section(section_id: int, name: str) -> bool:
    return await asyncio.to_thread(_update_section_sync, section_id, name)

async def clear_section_files(section_id: int):
    await asyncio.to_thread(_clear_section_files_sync, section_id)

async def update_series_settings(series_id: int, custom_msg=None, buttons_per_row=None, title=None, description=None, display_order=None):
    return await asyncio.to_thread(_update_series_settings_sync, series_id, custom_msg, buttons_per_row, title, description, display_order)

async def update_section_settings(section_id: int, custom_msg=None, buttons_per_row=None):
    return await asyncio.to_thread(_update_section_settings_sync, section_id, custom_msg, buttons_per_row)

async def add_file(file_code: str, message_id: int, file_name: str, file_size: int, mime_type: str, caption: str, series_id=None, episode_number=None, section_id=None):
    await asyncio.to_thread(_add_file_sync, file_code, message_id, file_name, file_size, mime_type, caption, series_id, episode_number, section_id)

async def get_file(file_code: str):
    return await asyncio.to_thread(_get_file_sync, file_code)

async def delete_file(file_code: str):
    return await asyncio.to_thread(_delete_file_sync, file_code)

async def list_files(skip=0, limit=20, search=None, series_id=None, section_id=None, filter_root=False):
    return await asyncio.to_thread(_list_files_sync, skip, limit, search, series_id, section_id, filter_root)

# --- Move Folder Sync Helpers ---
def _update_section_parent_sync(section_id: int, parent_id: int = None) -> bool:
    with SessionLocal() as session:
        sec = session.query(SeriesSection).filter(SeriesSection.id == section_id).first()
        if sec:
            sec.parent_id = parent_id
            session.commit()
            return True
        return False

def _list_all_folders_sync(series_id: int):
    with SessionLocal() as session:
        folders = session.query(SeriesSection).filter(
            SeriesSection.series_id == series_id,
            SeriesSection.sec_type == "folder"
        ).order_by(SeriesSection.id).all()
        return [{
            "id": f.id,
            "name": f.name,
            "series_id": f.series_id,
            "parent_id": f.parent_id,
            "sec_type": f.sec_type,
            "custom_msg": f.custom_msg,
            "buttons_per_row": f.buttons_per_row
        } for f in folders]

# --- Move Folder Async Helpers ---
async def update_section_parent(section_id: int, parent_id: int = None) -> bool:
    return await asyncio.to_thread(_update_section_parent_sync, section_id, parent_id)

async def list_all_folders(series_id: int):
    return await asyncio.to_thread(_list_all_folders_sync, series_id)

