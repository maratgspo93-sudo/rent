from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, Query, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .db import get_conn
from .fx import get_rate
from .normalize import to_usd, to_amd
from .scoring import price_flags
import json, os, time, uuid
from . import direct
from .photos import process_photo

app = FastAPI(title="Rental Hub Yerevan")
conn = get_conn()
STATIC = os.path.join(os.path.dirname(__file__), "static")

def _hours(iso):
    return round((datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds() / 3600, 1)

@app.get("/api/health")
def health():
    n = conn.execute("SELECT COUNT(*) FROM listings WHERE status='active'").fetchone()[0]
    return {"ok": True, "active_listings": n, "usd_amd": get_rate()}

@app.get("/api/listings")
def listings(district: Optional[str] = None, rooms: int = 0, max_price: Optional[float] = None,
             currency: str = "USD", pets: bool = False, heating: Optional[str] = None,
             new_building: bool = False, no_fee: bool = False, owner_only: bool = False,
             fresh_hours: Optional[float] = None, limit: int = Query(60, le=200)):
    rate = get_rate()
    groups = {}
    for r in conn.execute("SELECT * FROM listings WHERE status='active' ORDER BY last_checked DESC"):
        groups.setdefault(r["cluster_id"], []).append(dict(r))
    items = []
    for rows in groups.values():
        rep = rows[0]                                  # ամենաթարմ ստուգվածը
        usd = to_usd(rep["price_amount"], rep["price_currency"], rate)
        items.append({
            "id": rep["id"], "district": rep["district"], "rooms": rep["rooms"], "area": rep["area"],
            "floor": rep["floor"], "floors_total": rep["floors_total"],
            "price_amount": rep["price_amount"], "price_currency": rep["price_currency"],
            "price_usd": usd, "price_amd": to_amd(rep["price_amount"], rep["price_currency"], rate),
            "hours_since_check": _hours(rep["last_checked"]),
            "landlord": rep["landlord_label"], "pets": rep["pets"], "heating": rep["heating"],
            "new_building": rep["new_building"], "no_fee": rep["no_fee"], "is_demo": rep["is_demo"],
            "direct": rep["source"] == "direct", "contact_phone": rep["contact_phone"], "description": rep["description"],
            "street": rep["street"], "deposit": rep["deposit"], "declared_role": rep["declared_role"],
            "photo": ("/uploads/" + json.loads(rep["photos"])[0]) if rep["photos"] and json.loads(rep["photos"]) else None,
            "sources": [{"source": x["source"], "url": x["url"]} for x in rows],
        })
    price_flags(items)
    out = []
    for it in items:
        if district and it["district"] != district: continue
        if rooms and (it["rooms"] is None or (it["rooms"] < 3 if rooms == 3 else it["rooms"] != rooms)): continue
        if max_price:
            v = it["price_usd"] if currency == "USD" else it["price_amd"]
            if v is None or v > max_price: continue
        if pets and it["pets"] != 1: continue
        if heating and it["heating"] != heating: continue
        if new_building and it["new_building"] != 1: continue
        if no_fee and it["no_fee"] != 1: continue
        if owner_only and it["landlord"] != "owner": continue
        if fresh_hours and it["hours_since_check"] > fresh_hours: continue
        out.append(it)
    return {"rate": rate, "count": len(out), "items": out[:limit]}

UPLOADS = os.getenv("UPLOAD_DIR", "uploads")
os.makedirs(UPLOADS, exist_ok=True)
_hits = {}   # IP -> ժամանակներ (պարզ սահմանափակում. մի քանի սերվերի դեպքում փոխարինեք Redis-ով)

def _limited(ip, n=5, window=3600):
    now = time.time()
    _hits[ip] = [t for t in _hits.get(ip, []) if now - t < window]
    if len(_hits[ip]) >= n: return True
    _hits[ip].append(now); return False

@app.post("/api/submit")
async def submit(request: Request):
    if _limited(request.client.host if request.client else "?"):
        raise HTTPException(429, "Չափից շատ հայտարարություն այս ժամին. փորձեք ավելի ուշ")
    form = await request.form()
    clean, errors = direct.validate({k: form.get(k) for k in form.keys() if k != "photos"})
    files = [f for f in form.getlist("photos") if getattr(f, "filename", "")][:6]
    names, hashes = [], []
    for f in files:
        try:
            jpg, h = process_photo(await f.read())
        except ValueError as ex:
            errors["photos"] = str(ex); break
        name = uuid.uuid4().hex + ".jpg"
        with open(os.path.join(UPLOADS, name), "wb") as fh: fh.write(jpg)
        names.append(name); hashes.append(h)
    if errors:
        for n in names: os.remove(os.path.join(UPLOADS, n))
        raise HTTPException(422, errors)
    try:
        lid, token = direct.submit(conn, clean, names, hashes)
    except ValueError as ex:
        raise HTTPException(422, {"phone": str(ex)})
    return {"id": lid, "manage_token": token, "status": "pending"}

@app.get("/api/manage")
def manage_get(token: str):
    s = direct.summary(conn, token)
    if not s: raise HTTPException(404, "Չգտնվեց")
    return s

@app.post("/api/manage/confirm")
async def manage_confirm(request: Request):
    if not direct.confirm(conn, (await request.json()).get("token", "")): raise HTTPException(404, "Չգտնվեց")
    return {"ok": True}

@app.post("/api/manage/rented")
async def manage_rented(request: Request):
    if not direct.mark_rented(conn, (await request.json()).get("token", "")): raise HTTPException(404, "Չգտնվեց")
    return {"ok": True}

@app.get("/submit")
def submit_page():
    return FileResponse(os.path.join(STATIC, "submit.html"))

@app.get("/manage")
def manage_page():
    return FileResponse(os.path.join(STATIC, "manage.html"))

@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))

app.mount("/uploads", StaticFiles(directory=UPLOADS), name="uploads")
app.mount("/static", StaticFiles(directory=STATIC), name="static")
