import json
import asyncio
from datetime import datetime
from db_models import (
    engine, SessionLocal, db_init, Settings, Admin, User,
    CloneBot, Series, SeriesSection, FileRecord
)

def _export_db_backup_sync() -> str:
    with SessionLocal() as session:
        data = {}
        
        # 1. Settings
        settings_rows = session.query(Settings).all()
        data["settings"] = [{
            "id": s.id,
            "welcome_msg": s.welcome_msg,
            "fsub_channels": s.fsub_channels,
            "fsub_enabled": s.fsub_enabled,
            "custom_buttons": s.custom_buttons,
            "primary_clone_username": s.primary_clone_username,
            "db_channel_id": s.db_channel_id,
            "log_channel_id": s.log_channel_id,
            "auto_delete_enabled": s.auto_delete_enabled,
            "auto_delete_duration": s.auto_delete_duration
        } for s in settings_rows]

        # 2. Admins
        admins_rows = session.query(Admin).all()
        data["admins"] = [{"user_id": a.user_id} for a in admins_rows]

        # 3. Users
        users_rows = session.query(User).all()
        data["users"] = [{
            "user_id": u.user_id,
            "username": u.username,
            "first_name": u.first_name,
            "joined_at": u.joined_at.isoformat() if u.joined_at else None
        } for u in users_rows]

        # 4. CloneBots
        clone_bots_rows = session.query(CloneBot).all()
        data["clone_bots"] = [{
            "token": b.token,
            "username": b.username,
            "name": b.name,
            "is_active": b.is_active
        } for b in clone_bots_rows]

        # 5. Series
        series_rows = session.query(Series).all()
        data["series"] = [{
            "id": s.id,
            "title": s.title,
            "description": s.description,
            "custom_msg": s.custom_msg,
            "buttons_per_row": s.buttons_per_row
        } for s in series_rows]

        # 6. SeriesSections
        sections_rows = session.query(SeriesSection).all()
        data["series_sections"] = [{
            "id": s.id,
            "name": s.name,
            "series_id": s.series_id,
            "parent_id": s.parent_id,
            "sec_type": s.sec_type,
            "custom_msg": s.custom_msg,
            "buttons_per_row": s.buttons_per_row
        } for s in sections_rows]

        # 7. FileRecords
        files_rows = session.query(FileRecord).all()
        data["files"] = [{
            "file_code": f.file_code,
            "message_id": f.message_id,
            "file_name": f.file_name,
            "file_size": f.file_size,
            "mime_type": f.mime_type,
            "caption": f.caption,
            "series_id": f.series_id,
            "episode_number": f.episode_number,
            "section_id": f.section_id
        } for f in files_rows]

        return json.dumps(data, indent=4)

def _import_db_backup_sync(json_str: str) -> bool:
    data = json.loads(json_str)
    with SessionLocal() as session:
        try:
            # Delete in order of dependencies
            session.query(FileRecord).delete()
            session.query(SeriesSection).delete()
            session.query(Series).delete()
            session.query(CloneBot).delete()
            session.query(User).delete()
            session.query(Admin).delete()
            session.query(Settings).delete()
            session.flush()

            # 1. Restore settings
            for item in data.get("settings", []):
                s = Settings(
                    id=item.get("id", 1),
                    welcome_msg=item.get("welcome_msg"),
                    fsub_channels=item.get("fsub_channels"),
                    fsub_enabled=item.get("fsub_enabled"),
                    custom_buttons=item.get("custom_buttons"),
                    primary_clone_username=item.get("primary_clone_username"),
                    db_channel_id=item.get("db_channel_id"),
                    log_channel_id=item.get("log_channel_id"),
                    auto_delete_enabled=item.get("auto_delete_enabled", False),
                    auto_delete_duration=item.get("auto_delete_duration", 5)
                )
                session.add(s)

            # 2. Restore admins
            for item in data.get("admins", []):
                a = Admin(user_id=item.get("user_id"))
                session.add(a)

            # 3. Restore users
            for item in data.get("users", []):
                joined_str = item.get("joined_at")
                joined_at = datetime.fromisoformat(joined_str) if joined_str else datetime.utcnow()
                u = User(
                    user_id=item.get("user_id"),
                    username=item.get("username"),
                    first_name=item.get("first_name"),
                    joined_at=joined_at
                )
                session.add(u)

            # 4. Restore clone bots
            for item in data.get("clone_bots", []):
                cb = CloneBot(
                    token=item.get("token"),
                    username=item.get("username"),
                    name=item.get("name"),
                    is_active=item.get("is_active", False)
                )
                session.add(cb)

            # 5. Restore series
            for item in data.get("series", []):
                s = Series(
                    id=item.get("id"),
                    title=item.get("title"),
                    description=item.get("description"),
                    custom_msg=item.get("custom_msg"),
                    buttons_per_row=item.get("buttons_per_row", 2)
                )
                session.add(s)

            # 6. Restore series sections
            for item in data.get("series_sections", []):
                sec = SeriesSection(
                    id=item.get("id"),
                    name=item.get("name"),
                    series_id=item.get("series_id"),
                    parent_id=item.get("parent_id"),
                    sec_type=item.get("sec_type", "folder"),
                    custom_msg=item.get("custom_msg"),
                    buttons_per_row=item.get("buttons_per_row", 2)
                )
                session.add(sec)

            # 7. Restore file records
            for item in data.get("files", []):
                fr = FileRecord(
                    file_code=item.get("file_code"),
                    message_id=item.get("message_id"),
                    file_name=item.get("file_name"),
                    file_size=item.get("file_size"),
                    mime_type=item.get("mime_type"),
                    caption=item.get("caption"),
                    series_id=item.get("series_id"),
                    episode_number=item.get("episode_number"),
                    section_id=item.get("section_id")
                )
                session.add(fr)

            session.commit()
            return True
        except Exception as e:
            session.rollback()
            print(f"Error during backup import: {e}")
            raise e

def _restart_database_sync() -> bool:
    import db_models
    try:
        db_models.engine.dispose()
        from sqlalchemy import create_engine
        from config import DATABASE_URL
        db_models.engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
        db_models.SessionLocal.configure(bind=db_models.engine)
        db_init()
        return True
    except Exception as e:
        print(f"Failed to restart database connection: {e}")
        return False

# --- Async wrappers ---
async def export_db_backup() -> str:
    return await asyncio.to_thread(_export_db_backup_sync)

async def import_db_backup(json_str: str) -> bool:
    return await asyncio.to_thread(_import_db_backup_sync, json_str)

async def restart_database() -> bool:
    return await asyncio.to_thread(_restart_database_sync)
