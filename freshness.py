"""Օրիգինալ հղումների վերստուգում։ Գործարկել cron-ով (օր. ամեն 6 ժամը մեկ)։
Telegram-ի համար t.me հղումը 200 է տալիս նաև ջնջված հաղորդագրության դեպքում,
ուստի այդ աղբյուրը ստուգվում է collectors/telegram_collector.py-ի refresh_telegram-ով։"""
import time, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone

UA = "RentalHubBot/0.1 (+contact: set-your-email@example.com)"   # փոխեք ձեր կոնտակտով

def check_url(url, timeout=15):
    """-> 'ok' | 'gone' | 'unknown'"""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return "ok" if r.status == 200 else "unknown"
    except urllib.error.HTTPError as e:
        return "gone" if e.code in (404, 410) else "unknown"
    except Exception:
        return "unknown"

def check_all(conn, older_than_hours=6, pause=3.0):
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=older_than_hours)).isoformat(timespec="seconds")
    rows = conn.execute("""SELECT id,url FROM listings WHERE status='active' AND is_demo=0
                           AND source!='telegram' AND last_checked < ?""", (cutoff,)).fetchall()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for r in rows:
        res = check_url(r["url"])
        if res == "ok":
            conn.execute("UPDATE listings SET last_checked=? WHERE id=?", (now, r["id"]))
        elif res == "gone":
            conn.execute("UPDATE listings SET status='gone', last_checked=? WHERE id=?", (now, r["id"]))
        conn.commit()
        time.sleep(pause)      # դանդաղ՝ աղբյուրը չբեռնելու համար
    return len(rows)

if __name__ == "__main__":
    from .db import get_conn
    print("checked:", check_all(get_conn()))
