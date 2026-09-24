"""Հրապարակային Telegram ալիքների հավաքում Telethon-ով (օգտատիրոջ API, ոչ թե բոտ)։
API_ID/API_HASH՝ https://my.telegram.org → API development tools։
Առաջին գործարկման ժամանակ Telethon-ը կխնդրի հեռախոսահամարը և կոդը։
Գործարկում՝ python -m collectors.telegram_collector
ՉԵՄ ԱՐԵԼ ԱՅՍՏԵՂԻՑ. այս ֆայլը չի փորձարկվել իրական հաշվով, ստուգեք ձեր մոտ։"""
import asyncio, io, os
from telethon import TelegramClient
from app.db import get_conn
from app.ingest import ingest

def _dhash(data):
    import imagehash
    from PIL import Image
    return str(imagehash.dhash(Image.open(io.BytesIO(data))))

async def collect(limit=100):
    conn = get_conn()
    channels = [c.strip() for c in os.environ["TG_CHANNELS"].split(",") if c.strip()]
    async with TelegramClient("rentalhub", int(os.environ["TG_API_ID"]), os.environ["TG_API_HASH"]) as client:
        for ch in channels:
            async for m in client.iter_messages(ch, limit=limit):
                if not m.text:
                    continue
                images = []
                if m.photo:
                    try:
                        images.append(_dhash(await client.download_media(m, file=bytes)))
                    except Exception:
                        pass
                lid, action = ingest(conn, dict(source="telegram", source_id=f"{ch}:{m.id}",
                                                url=f"https://t.me/{ch}/{m.id}", text=m.text, images=images))
                print(ch, m.id, action)
            await asyncio.sleep(2)

async def refresh_telegram():
    """Ջնջված հաղորդագրությունները նշում է 'gone'։"""
    conn = get_conn()
    rows = conn.execute("SELECT id, source_id FROM listings WHERE source='telegram' AND status='active' AND is_demo=0").fetchall()
    by_ch = {}
    for r in rows:
        ch, mid = r["source_id"].rsplit(":", 1)
        by_ch.setdefault(ch, {})[int(mid)] = r["id"]
    async with TelegramClient("rentalhub", int(os.environ["TG_API_ID"]), os.environ["TG_API_HASH"]) as client:
        for ch, ids in by_ch.items():
            msgs = await client.get_messages(ch, ids=list(ids))
            for mid, msg in zip(ids, msgs):
                q = "UPDATE listings SET status='gone' WHERE id=?" if msg is None else \
                    "UPDATE listings SET last_checked=datetime('now') WHERE id=?"
                conn.execute(q, (ids[mid],))
        conn.commit()

if __name__ == "__main__":
    asyncio.run(collect())
