"""Load known students' Telegram usernames. Usage: python -m scripts.add_students students.txt
File format: one username per line (with or without @); optional note after a comma."""
import asyncio
import sys

import asyncpg

from app.config import settings


async def main(path: str):
    rows = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, _, note = line.partition(",")
        rows.append((name.strip().lstrip("@"), note.strip() or None))
    conn = await asyncpg.connect(settings.database_url)
    await conn.executemany(
        "INSERT INTO allowed_students (telegram_username, note) VALUES ($1, $2) ON CONFLICT (telegram_username) DO NOTHING", rows)
    await conn.close()
    print(f"{len(rows)} usernames processed")


asyncio.run(main(sys.argv[1]))
