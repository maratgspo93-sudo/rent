"""Տանտեր/միջնորդ միավոր և կասկածելի գնի նշում։ Արդյունքը միշտ «հավանաբար» է։"""
import re, statistics

AGENT_WORDS = r"գործակալություն|ռիելթոր|օբյեկտի կոդ|կոդ\s*[:№]|агентств|риелтор|риэлтор|код объекта|agency|realtor"
FEE_WORDS = r"միջնորդավճար|комисси|commission"
OWNER_WORDS = r"տանտեր|от хозяина|owner"
NOFEE = r"առանց միջնորդավճար|առանց միջնորդ|без комисс|без посредник"

def landlord_score(text, listings_with_same_phone=0):
    """Դրական՝ միջնորդ, բացասական՝ տանտեր։ -> (score, 'agent'|'owner'|'unknown')"""
    t = (text or "").lower()
    s = 0
    s += 3 if re.search(AGENT_WORDS, t) else 0
    s += 2 if re.search(FEE_WORDS, re.sub(NOFEE, "", t)) else 0   # «առանց միջնորդավճար»-ը գործակալ չի նշանակում
    s -= 1 if re.search(OWNER_WORDS, t) else 0                     # գործակալները նույնպես գրում են՝ թույլ կշիռ
    if listings_with_same_phone >= 5: s += 4
    elif listings_with_same_phone >= 3: s += 3
    label = "agent" if s >= 3 else "owner" if s <= -1 or (s == 0 and listings_with_same_phone == 0 and _owner_hint(t)) else "unknown"
    return s, label

def _owner_hint(t):
    return False   # միտումնավոր՝ առանց ազդանշանի «տանտեր» չենք նշում

def price_flags(items, min_group=5, ratio=0.65):
    """items՝ dict-եր՝ district, rooms, price_usd։ Ավելացնում է item['price_flag']='low' մեդիանից ցածր գնի համար։"""
    groups = {}
    for it in items:
        if it.get("price_usd") and it.get("district") and it.get("rooms"):
            groups.setdefault((it["district"], min(it["rooms"], 3)), []).append(it["price_usd"])
    med = {k: statistics.median(v) for k, v in groups.items() if len(v) >= min_group}
    for it in items:
        m = med.get((it.get("district"), min(it.get("rooms") or 0, 3)))
        it["price_flag"] = "low" if m and it.get("price_usd") and it["price_usd"] < ratio * m else None
    return items
