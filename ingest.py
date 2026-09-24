import json
from datetime import datetime, timezone
from .normalize import (parse_price, parse_district, parse_rooms, parse_area, parse_floor,
                        parse_features, extract_phone, phone_hash)
from .dedupe import find_match
from .scoring import landlord_score

def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def ingest(conn, raw, now=None):
    """raw: source, source_id, url, text, [images: list[hex dHash]], [phone], [is_demo]
    -> (listing_id, action) action ∈ 'seen' | 'merged' | 'review' | 'new'"""
    now = now or _now()
    ex = conn.execute("SELECT id FROM listings WHERE source=? AND source_id=?",
                      (raw["source"], raw["source_id"])).fetchone()
    if ex:
        conn.execute("UPDATE listings SET last_seen=?, last_checked=?, status='active' WHERE id=?", (now, now, ex["id"]))
        conn.commit(); return ex["id"], "seen"

    text = raw["text"]
    amount, cur = parse_price(text)
    if amount is None:
        return None, "skipped_no_price"
    floor, floors_total = parse_floor(text)
    f = parse_features(text)
    phone = raw.get("phone") or extract_phone(text)
    ph = phone_hash(phone)
    new = dict(district=parse_district(text), rooms=parse_rooms(text), area=parse_area(text), floor=floor,
               phone_hash=ph, text=text, image_hashes=list(raw.get("images", [])))

    cands = []
    for r in conn.execute("SELECT * FROM listings WHERE status='active'"):
        c = dict(r); c["image_hashes"] = json.loads(c["image_hashes"]); cands.append(c)
    match, score, decision = find_match(new, cands)

    same_phone = conn.execute("SELECT COUNT(DISTINCT cluster_id) FROM listings WHERE phone_hash=?", (ph,)).fetchone()[0] if ph else 0
    lscore, llabel = landlord_score(text, same_phone)

    cur_ = conn.execute(
        """INSERT INTO listings(source,source_id,url,title,text,price_amount,price_currency,district,rooms,area,floor,
           floors_total,pets,heating,new_building,no_fee,phone_hash,image_hashes,cluster_id,landlord_score,landlord_label,
           first_seen,last_seen,last_checked,is_demo) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (raw["source"], raw["source_id"], raw["url"], text[:80], text, amount, cur, new["district"], new["rooms"],
         new["area"], floor, floors_total, f["pets"], f["heating"], f["new_building"], f["no_fee"], ph,
         json.dumps(new["image_hashes"]), match["cluster_id"] if decision == "merge" else None,
         lscore, llabel, now, now, now, int(raw.get("is_demo", 0))))
    lid = cur_.lastrowid
    if decision != "merge":
        conn.execute("UPDATE listings SET cluster_id=id WHERE id=?", (lid,))
    if decision == "review":
        conn.execute("INSERT OR REPLACE INTO dedupe_review VALUES(?,?,?)", (lid, match["id"], score))
    conn.commit()
    return lid, {"merge": "merged", "review": "review", "new": "new"}[decision]
