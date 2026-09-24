import os, sqlite3

NEW_COLS = {   # ուղիղ (տանտերերի) հայտարարությունների դաշտեր
    "contact_phone": "TEXT", "description": "TEXT", "street": "TEXT",
    "photos": "TEXT NOT NULL DEFAULT '[]'", "deposit": "INTEGER", "declared_role": "TEXT", "token_hash": "TEXT",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL, source_id TEXT NOT NULL, url TEXT NOT NULL,
  title TEXT, text TEXT,
  price_amount REAL, price_currency TEXT,           -- бնօրինակ գին և արժույթ (կարող է NULL լինել)
  district TEXT, rooms INTEGER, area REAL, floor INTEGER, floors_total INTEGER,
  pets INTEGER, heating TEXT, new_building INTEGER, no_fee INTEGER,
  phone_hash TEXT,                                   -- միայն sha256, հեռախոսը չենք պահում
  image_hashes TEXT NOT NULL DEFAULT '[]',           -- JSON՝ dHash hex ցուցակ
  cluster_id INTEGER, landlord_score INTEGER DEFAULT 0, landlord_label TEXT DEFAULT 'unknown',
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, last_checked TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',             -- pending | active | gone | rejected
  is_demo INTEGER NOT NULL DEFAULT 0,
  contact_phone TEXT, description TEXT, street TEXT, photos TEXT NOT NULL DEFAULT '[]',
  deposit INTEGER, declared_role TEXT, token_hash TEXT,
  UNIQUE(source, source_id)
);
CREATE INDEX IF NOT EXISTS ix_l_cluster ON listings(cluster_id);
CREATE INDEX IF NOT EXISTS ix_l_phone ON listings(phone_hash);
CREATE TABLE IF NOT EXISTS dedupe_review(
  a_id INTEGER, b_id INTEGER, score INTEGER, PRIMARY KEY(a_id,b_id)
);
"""

def get_conn(path=None):
    conn = sqlite3.connect(path or os.getenv("DB_PATH", "rentalhub.db"), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    have = {r[1] for r in conn.execute("PRAGMA table_info(listings)")}
    for col, ddl in NEW_COLS.items():          # հին բազաների միգրացիա
        if col not in have:
            conn.execute(f"ALTER TABLE listings ADD COLUMN {col} {ddl}")
    conn.commit()
    return conn
