"""Տանտերերի ուղիղ հայտարարություններ. ստացում, մոդերացիա, «դեռ ազատ է» հաստատում, ժամկետանց։
CLI՝ python -m app.direct pending | approve ID | reject ID | expire"""
import hashlib, json, re, secrets, sys
from datetime import datetime, timedelta, timezone
from .normalize import DISTRICTS, phone_hash
from .dedupe import find_match
from .scoring import landlord_score

MAX_PER_PHONE = 5          # մեկ համարից առավելագույնը ակտիվ/սպասող հայտարարություններ
EXPIRE_DAYS = 14           # առանց հաստատման հայտարարությունը թաքցվում է

def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def normalize_phone(s):
    d = re.sub(r"\D", "", s or "")
    if d.startswith("374") and len(d) == 11: return "+" + d
    if d.startswith("0") and len(d) == 9: return "+374" + d[1:]
    return None

def _int(v):
    try: return int(str(v).strip())
    except (TypeError, ValueError): return None

def _flt(v):
    try: return float(str(v).replace(",", ".").replace(" ", ""))
    except (TypeError, ValueError): return None

def _flag(v):
    return 1 if str(v).lower() in ("1", "true", "on", "yes") else 0

def validate(d):
    """-> (clean, errors). errors՝ {դաշտ: հաղորդագրություն}"""
    e, c = {}, {}
    if d.get("website"): e["_"] = "spam"                 # honeypot
    c["district"] = d.get("district")
    if c["district"] not in DISTRICTS: e["district"] = "Ընտրեք շրջանը"
    c["street"] = (d.get("street") or "").strip()[:80]
    c["rooms"] = _int(d.get("rooms"))
    if not c["rooms"] or not 1 <= c["rooms"] <= 10: e["rooms"] = "Սենյակների քանակը 1-10 է"
    c["area"] = _flt(d.get("area"))
    if not c["area"] or not 5 <= c["area"] <= 1000: e["area"] = "Մակերեսը 5-1000 մ² է"
    c["floor"], c["floors_total"] = _int(d.get("floor")), _int(d.get("floors_total"))
    if c["floor"] is None or c["floors_total"] is None or not 0 <= c["floor"] <= c["floors_total"] <= 60:
        e["floor"] = "Նշեք հարկը և շենքի հարկերի քանակը (հարկը չի կարող մեծ լինել)"
    c["price_amount"], c["price_currency"] = _flt(d.get("price_amount")), d.get("price_currency")
    lim = {"USD": (50, 20000), "AMD": (20000, 10_000_000)}.get(c["price_currency"])
    if not lim: e["price_currency"] = "Ընտրեք արժույթը"
    elif c["price_amount"] is None or not lim[0] <= c["price_amount"] <= lim[1]:
        e["price_amount"] = f"Գինը պետք է լինի {lim[0]}-{lim[1]} {c['price_currency']} միջակայքում"
    c["description"] = (d.get("description") or "").strip()[:2000]
    c["pets"], c["new_building"], c["no_fee"], c["deposit"] = (_flag(d.get(k)) for k in ("pets", "new_building", "no_fee", "deposit"))
    c["heating"] = d.get("heating") if d.get("heating") in ("central", "baxi", "electric") else None
    c["role"] = d.get("role")
    if c["role"] not in ("owner", "agent"): e["role"] = "Նշեք՝ տանտեր եք, թե միջնորդ"
    c["phone"] = normalize_phone(d.get("phone"))
    if not c["phone"]: e["phone"] = "Մուտքագրեք ՀՀ հեռախոսահամար (օր. 077 12 34 56)"
    if not _flag(d.get("consent")): e["consent"] = "Անհրաժեշտ է համաձայնություն՝ համարը հրապարակելու համար"
    return c, e

def _find(conn, token):
    h = hashlib.sha256(token.encode()).hexdigest()
    return conn.execute("SELECT * FROM listings WHERE token_hash=? AND source='direct'", (h,)).fetchone()

def submit(conn, c, photo_names=(), photo_hashes=(), now=None):
    """-> (id, token). Հայտարարությունը մտնում է 'pending', մինչև մոդերատորը հաստատի։ ValueError՝ սահմանաչափի դեպքում։"""
    now = now or _now()
    ph = phone_hash(c["phone"])
    n = conn.execute("SELECT COUNT(*) FROM listings WHERE source='direct' AND phone_hash=? AND status IN ('pending','active')", (ph,)).fetchone()[0]
    if n >= MAX_PER_PHONE: raise ValueError("Այս համարով արդեն չափից շատ հայտարարություն կա")
    role = c["role"]
    if role == "owner" and n >= 2: role = "agent"       # 3-րդ բնակարանից սկսած՝ համարը միջնորդի է նման
    label = "agent" if role == "agent" else "owner"
    token = secrets.token_urlsafe(24)
    text = f"{c['district']} {c['rooms']} սենյակ {c['area']} մ² {c['floor']}/{c['floors_total']} հարկ {c['description']}"
    cur = conn.execute(
        """INSERT INTO listings(source,source_id,url,title,text,price_amount,price_currency,district,rooms,area,floor,floors_total,
           pets,heating,new_building,no_fee,phone_hash,image_hashes,landlord_score,landlord_label,first_seen,last_seen,last_checked,
           status,contact_phone,description,street,photos,deposit,declared_role,token_hash)
           VALUES('direct',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'pending',?,?,?,?,?,?,?)""",
        (secrets.token_hex(8), "", text[:80], text, c["price_amount"], c["price_currency"], c["district"], c["rooms"], c["area"],
         c["floor"], c["floors_total"], c["pets"], c["heating"], c["new_building"], c["no_fee"], ph, json.dumps(list(photo_hashes)),
         0, label, now, now, now, c["phone"], c["description"], c["street"], json.dumps(list(photo_names)), c["deposit"], c["role"],
         hashlib.sha256(token.encode()).hexdigest()))
    lid = cur.lastrowid
    conn.execute("UPDATE listings SET cluster_id=id, url=? WHERE id=?", (f"/#l{lid}", lid))
    new = dict(district=c["district"], rooms=c["rooms"], area=c["area"], floor=c["floor"], phone_hash=ph,
               text=text, image_hashes=list(photo_hashes))
    cands = []
    for r in conn.execute("SELECT * FROM listings WHERE status='active'"):
        x = dict(r); x["image_hashes"] = json.loads(x["image_hashes"]); cands.append(x)
    m, score, decision = find_match(new, cands)
    if decision in ("merge", "review"):                # ուղիղ հայտարարությունները երբեք ավտոմատ չեն միավորվում
        conn.execute("INSERT OR REPLACE INTO dedupe_review VALUES(?,?,?)", (lid, m["id"], score))
    conn.commit()
    return lid, token

def pending(conn):
    return conn.execute("""SELECT l.*, (SELECT MAX(score) FROM dedupe_review WHERE a_id=l.id) AS dup_score
                           FROM listings l WHERE source='direct' AND status='pending' ORDER BY id""").fetchall()

def approve(conn, lid, now=None):
    now = now or _now()
    n = conn.execute("UPDATE listings SET status='active', last_checked=?, last_seen=? WHERE id=? AND source='direct' AND status='pending'", (now, now, lid)).rowcount
    conn.commit(); return n == 1

def reject(conn, lid):
    n = conn.execute("UPDATE listings SET status='rejected' WHERE id=? AND source='direct' AND status='pending'", (lid,)).rowcount
    conn.commit(); return n == 1

def confirm(conn, token, now=None):
    """«Դեռ ազատ է». թարմացնում է ստուգման ժամանակը։ Չի վերակենդանացնում մերժվածները/սպասողները։"""
    r = _find(conn, token)
    if not r or r["status"] not in ("active", "gone"): return False
    conn.execute("UPDATE listings SET last_checked=?, last_seen=?, status='active' WHERE id=?", (now or _now(),) * 2 + (r["id"],))
    conn.commit(); return True

def mark_rented(conn, token):
    r = _find(conn, token)
    if not r or r["status"] not in ("active", "pending"): return False
    conn.execute("UPDATE listings SET status='gone' WHERE id=?", (r["id"],)); conn.commit(); return True

def summary(conn, token):
    r = _find(conn, token)
    return None if not r else {k: r[k] for k in ("id", "district", "rooms", "price_amount", "price_currency", "status", "last_checked")}

def expire_stale(conn, days=EXPIRE_DAYS, now=None):
    now_dt = datetime.fromisoformat(now) if now else datetime.now(timezone.utc)
    cutoff = (now_dt - timedelta(days=days)).isoformat(timespec="seconds")
    n = conn.execute("UPDATE listings SET status='gone' WHERE source='direct' AND status='active' AND last_checked < ?", (cutoff,)).rowcount
    conn.commit(); return n

if __name__ == "__main__":
    from .db import get_conn
    conn, a = get_conn(), sys.argv[1:]
    if a[:1] == ["pending"]:
        for r in pending(conn):
            print(r["id"], r["district"], r["rooms"], r["price_amount"], r["price_currency"], r["contact_phone"], r["declared_role"],
                  f"(հնարավոր կրկնօրինակ՝ {r['dup_score']})" if r["dup_score"] else "")
    elif a[:1] == ["approve"]: print(approve(conn, int(a[1])))
    elif a[:1] == ["reject"]: print(reject(conn, int(a[1])))
    elif a[:1] == ["expire"]: print("expired:", expire_stale(conn))
    else: print(__doc__)
