import asyncio
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from aiogram import Bot
from aiogram.types import BufferedInputFile, FSInputFile

from bot.config import settings

logger = logging.getLogger(__name__)

BACKUP_DIR = Path("backups")


async def run_backup(bot: Bot) -> None:
    """
    Dump the PostgreSQL database with pg_dump and send the compressed file
    to the owner via Telegram.  Requires pg_dump on PATH (standard in any
    postgres-client install).
    """
    BACKUP_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_file = BACKUP_DIR / f"backup_{timestamp}.sql.gz"

    parsed = urlparse(settings.database_url.replace("+asyncpg", ""))
    db_name = parsed.path.lstrip("/")
    db_user = parsed.username or "postgres"
    db_host = parsed.hostname or "localhost"
    db_port = str(parsed.port or 5432)
    db_pass = parsed.password or ""

    env = os.environ.copy()
    if db_pass:
        env["PGPASSWORD"] = db_pass

    cmd = [
        "pg_dump",
        "-h", db_host,
        "-p", db_port,
        "-U", db_user,
        "-d", db_name,
        "--no-owner",
        "--no-acl",
        "-Fc",  # custom compressed format
        "-f", str(out_file),
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            err = stderr.decode(errors="replace")
            logger.error("pg_dump failed: %s", err)
            await bot.send_message(
                chat_id=settings.owner_id,
                text=f"❌ Backup failed:\n<pre>{err[:1000]}</pre>",
                parse_mode="HTML",
            )
            return

        file_size_mb = out_file.stat().st_size / (1024 * 1024)
        file = FSInputFile(str(out_file), filename=out_file.name)
        await bot.send_document(
            chat_id=settings.owner_id,
            document=file,
            caption=f"💾 Еженедельный бэкап БД\n📅 {timestamp}\n📦 {file_size_mb:.1f} MB",
        )
        logger.info("Backup sent to owner: %s (%.1f MB)", out_file.name, file_size_mb)

    except FileNotFoundError:
        msg = "❌ pg_dump не найден. Установите postgresql-client."
        logger.error(msg)
        await bot.send_message(chat_id=settings.owner_id, text=msg)
    except Exception:
        logger.exception("Unexpected backup error")
    finally:
        # Keep only the last 5 backups
        backups = sorted(BACKUP_DIR.glob("backup_*.sql.gz"))
        for old in backups[:-5]:
            old.unlink(missing_ok=True)
