"""Տեքստից պարամետրերի հանում. Ոչինչ չենք գուշակում՝ եթե չգիտենք, վերադարձնում ենք None։"""
import re, hashlib

DISTRICTS = {
    "Աջափնյակ": ["աջափնյակ", "ajapnyak", "ажапняк"],
    "Ավան": ["ավան", "avan", "аван"],
    "Արաբկիր": ["արաբկիր", "arabkir", "арабкир"],
    "Դավթաշեն": ["դավթաշեն", "davtashen", "давташен"],
    "Էրեբունի": ["էրեբունի", "erebuni", "эребуни"],
    "Կենտրոն": ["կենտրոն", "kentron", "центр"],
    "Մալաթիա-Սեբաստիա": ["մալաթիա", "սեբաստիա", "malatia", "малатия"],
    "Նոր Նորք": ["նոր նորք", "nor nork", "нор норк"],
    "Նորք-Մարաշ": ["նորք-մարաշ", "նորք մարաշ", "nork-marash", "норк-мараш"],
    "Նուբարաշեն": ["նուբարաշեն", "nubarashen", "нубарашен"],
    "Շենգավիթ": ["շենգավիթ", "shengavit", "шенгавит"],
    "Քանաքեռ-Զեյթուն": ["քանաքեռ", "զեյթուն", "kanaker", "канакер"],
}
_ALIASES = sorted(((a, d) for d, al in DISTRICTS.items() for a in al), key=lambda x: -len(x[0]))

def parse_district(text):
    t = text.lower()
    for alias, d in _ALIASES:          # ամենաերկար alias-ը առաջինն է («նոր նորք» < «նորք-մարաշ»)
        if alias in t:
            return d
    return None

_NUM = r"\d{1,3}(?:[ ,\u00a0.]\d{3})+|\d+"
_USD = r"\$|usd|դոլար\w*|доллар\w*"
_AMD = r"֏|amd|դրամ\w*|драм\w*|դր\b\.?"
_P1 = re.compile(rf"(?P<c>\$)\s*(?P<n>{_NUM})", re.I)
_P2 = re.compile(rf"(?P<n>{_NUM})\s*(?P<c>{_USD}|{_AMD})", re.I)
_P3 = re.compile(rf"(?:գին|цена|price)\D{{0,6}}(?P<n>{_NUM})", re.I)

def _cur(tok):
    return "USD" if re.fullmatch(_USD, tok, re.I) else "AMD"

def _amt(s):
    return float(re.sub(r"\D", "", s))

def parse_price(text):
    """-> (amount, currency|None). Արժույթը չգտնվելու դեպքում currency=None (ձեռքով ստուգման)։"""
    for m in _P1.finditer(text):
        return _amt(m["n"]), "USD"
    for m in _P2.finditer(text):
        return _amt(m["n"]), _cur(m["c"])
    m = _P3.search(text)
    if m:
        return _amt(m["n"]), None
    return None, None

def to_amd(amount, currency, rate):
    if amount is None or currency is None: return None
    return amount if currency == "AMD" else amount * rate

def to_usd(amount, currency, rate):
    if amount is None or currency is None: return None
    return amount if currency == "USD" else amount / rate

def parse_rooms(text):
    m = re.search(r"(\d)\s*[-\s]?\s*(?:սենյակ|սեն\.|комн|room)", text, re.I)
    return int(m[1]) if m else None

def parse_area(text):
    m = re.search(r"(\d{2,3}(?:[.,]\d)?)\s*(?:մ²|մ2|քմ|քառ|м²|м2|m2|m²|sq)", text, re.I)
    return float(m[1].replace(",", ".")) if m else None

def parse_floor(text):
    m = re.search(r"(\d{1,2})\s*/\s*(\d{1,2})\s*հարկ", text) or \
        re.search(r"հարկ\s*[:\-]?\s*(\d{1,2})\s*/\s*(\d{1,2})", text)
    return (int(m[1]), int(m[2])) if m else (None, None)

def _yn(text, yes, no):
    t = text.lower()
    if re.search(no, t): return 0
    if re.search(yes, t): return 1
    return None

def parse_features(text):
    t = text.lower()
    heating = "central" if re.search(r"կենտրոնացված|центральн", t) else \
              "baxi" if re.search(r"baxi|բաքսի|бакси|ավտոնոմ", t) else None
    return {
        "pets": _yn(t, r"կենդանիներ\w*\s+(?:թույլ|ընդունելի)|с животными|pets? (?:ok|allowed)",
                    r"առանց կենդանի|без животных|no pets"),
        "heating": heating,
        "new_building": 1 if re.search(r"նորակառույց|новостройк|new building", t) else None,
        "no_fee": 1 if re.search(r"առանց միջնորդավճար|առանց միջնորդ|без комисс|без посредник", t) else None,
    }

_PHONE = re.compile(r"(?:\+374|\b0)[\s\-()]*(\d{2})[\s\-)]*(\d{2})[\s\-]*(\d{2})[\s\-]*(\d{2})\b")

def extract_phone(text):
    m = _PHONE.search(text)
    return "+374" + "".join(m.groups()) if m else None

def phone_hash(phone):
    return hashlib.sha256(phone.encode()).hexdigest()[:24] if phone else None
