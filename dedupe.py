"""Նույն բնակարանի կրկնօրինակների ճանաչում՝ կշռված ազդանշանների գումարով։"""
import re

MERGE, REVIEW = 60, 40

def hamming(a, b):
    return bin(int(a, 16) ^ int(b, 16)).count("1")

def shared_images(A, B, thr=6):
    return sum(1 for a in A if any(hamming(a, b) <= thr for b in B))

def _tok(t):
    return {w for w in re.findall(r"\w+", (t or "").lower()) if len(w) >= 4}

def jaccard(a, b):
    A, B = _tok(a), _tok(b)
    return len(A & B) / len(A | B) if A and B else 0.0

def pair_score(a, b):
    s = 0
    n = shared_images(a["image_hashes"], b["image_hashes"])
    s += 55 if n >= 2 else 30 if n == 1 else 0
    if a["district"] and b["district"]:
        s += 10 if a["district"] == b["district"] else -50
    if a["rooms"] and b["rooms"]:
        s += 10 if a["rooms"] == b["rooms"] else -40
    if a["area"] and b["area"]:
        d = abs(a["area"] - b["area"])
        s += 10 if d <= 3 else -25 if d > 8 else 0
    if a["floor"] and b["floor"] and a["floor"] == b["floor"]:
        s += 5
    if a["phone_hash"] and a["phone_hash"] == b["phone_hash"]:
        s += 10
    j = jaccard(a["text"], b["text"])
    s += 15 if j >= 0.6 else 7 if j >= 0.4 else 0
    return s

def find_match(new, candidates):
    """-> (candidate|None, score, 'merge'|'review'|'new')"""
    best, best_s = None, -999
    for c in candidates:
        s = pair_score(new, c)
        if s > best_s: best, best_s = c, s
    if best is None: return None, 0, "new"
    return best, best_s, "merge" if best_s >= MERGE else "review" if best_s >= REVIEW else "new"
