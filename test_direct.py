import unittest
from app.db import get_conn
from app.direct import validate, submit, approve, reject, confirm, mark_rented, expire_stale, pending, normalize_phone, summary
from app.photos import sniff

def form(**kw):
    d = dict(district="Կենտրոն", street="Աբովյան", rooms="2", area="64", floor="5", floors_total="9",
             price_amount="650", price_currency="USD", role="owner", phone="077 12 34 56", consent="on")
    d.update(kw); return d

class T(unittest.TestCase):
    def test_phone(self):
        self.assertEqual(normalize_phone("077 12 34 56"), "+37477123456")
        self.assertEqual(normalize_phone("+374 (93) 22-33-44"), "+37493223344")
        self.assertIsNone(normalize_phone("12345"))
    def test_validate(self):
        c, e = validate(form()); self.assertEqual(e, {}); self.assertEqual(c["phone"], "+37477123456")
        self.assertIn("floor", validate(form(floor="12"))[1])
        self.assertIn("price_amount", validate(form(price_amount="5"))[1])
        self.assertIn("price_amount", validate(form(price_currency="AMD", price_amount="650"))[1])
        self.assertIn("consent", validate(form(consent=""))[1])
        self.assertIn("district", validate(form(district="Լոնդոն"))[1])
        self.assertIn("_", validate(form(website="http://spam"))[1])
    def test_lifecycle(self):
        c = get_conn(":memory:")
        lid, tok = submit(c, validate(form())[0], now="2026-09-01T10:00:00+00:00")
        self.assertEqual(len(pending(c)), 1)
        self.assertFalse(confirm(c, tok))                       # սպասողը չի վերակենդանանում
        self.assertTrue(approve(c, lid, now="2026-09-01T12:00:00+00:00"))
        self.assertEqual(expire_stale(c, now="2026-09-10T12:00:00+00:00"), 0)   # 9 օր
        self.assertEqual(expire_stale(c, now="2026-09-20T12:00:00+00:00"), 1)   # 19 օր
        self.assertEqual(summary(c, tok)["status"], "gone")
        self.assertTrue(confirm(c, tok, now="2026-09-21T00:00:00+00:00"))       # տանտերը հաստատեց
        self.assertEqual(summary(c, tok)["status"], "active")
        self.assertTrue(mark_rented(c, tok)); self.assertEqual(summary(c, tok)["status"], "gone")
        self.assertFalse(confirm(c, "wrong-token"))
    def test_reject(self):
        c = get_conn(":memory:"); lid, tok = submit(c, validate(form())[0])
        self.assertTrue(reject(c, lid)); self.assertFalse(approve(c, lid)); self.assertFalse(confirm(c, tok))
    def test_token_not_stored_plain(self):
        c = get_conn(":memory:"); lid, tok = submit(c, validate(form())[0])
        self.assertNotIn(tok, str(tuple(c.execute("SELECT * FROM listings").fetchone())))
    def test_phone_limits_and_agent_flag(self):
        c = get_conn(":memory:")
        for i in range(5): submit(c, validate(form(floor=str(i)))[0])
        with self.assertRaises(ValueError): submit(c, validate(form())[0])
        labels = [r[0] for r in c.execute("SELECT landlord_label FROM listings ORDER BY id")]
        self.assertEqual(labels, ["owner", "owner", "agent", "agent", "agent"])
    def test_duplicate_goes_to_review(self):
        c = get_conn(":memory:")
        a, _ = submit(c, validate(form())[0], photo_hashes=["f0f0f0f0f0f0f0f0"]); approve(c, a)
        b, _ = submit(c, validate(form(phone="099 11 22 33"))[0], photo_hashes=["f0f0f0f0f0f0f0f1"])
        self.assertIsNotNone(c.execute("SELECT 1 FROM dedupe_review WHERE a_id=?", (b,)).fetchone())
        self.assertEqual(c.execute("SELECT status FROM listings WHERE id=?", (b,)).fetchone()[0], "pending")
    def test_sniff(self):
        self.assertEqual(sniff(b"\xff\xd8\xff\xe0abc"), "jpeg"); self.assertIsNone(sniff(b"<?php"))

if __name__ == "__main__":
    unittest.main()
