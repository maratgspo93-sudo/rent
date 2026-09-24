import unittest, json
from app.db import get_conn
from app.ingest import ingest
from app.normalize import parse_price, parse_district, parse_rooms, parse_area, parse_floor, parse_features, extract_phone
from app.dedupe import hamming, pair_score
from app.scoring import landlord_score, price_flags

class T(unittest.TestCase):
    def test_price(self):
        self.assertEqual(parse_price("Գինը՝ 650$"), (650.0, "USD"))
        self.assertEqual(parse_price("650 դոլար"), (650.0, "USD"))
        self.assertEqual(parse_price("180 000 դրամ"), (180000.0, "AMD"))
        self.assertEqual(parse_price("150 000 դր. զանգ"), (150000.0, "AMD"))
        self.assertEqual(parse_price("250000 ֏"), (250000.0, "AMD"))
        self.assertEqual(parse_price("գին՝ 300000"), (300000.0, None))   # արժույթը չենք գուշակում
        self.assertEqual(parse_price("2 սենյակ, զանգահարել"), (None, None))
    def test_params(self):
        self.assertEqual(parse_district("Նոր Նորք, 1 սենյակ"), "Նոր Նորք")
        self.assertEqual(parse_district("Նորք-Մարաշ 3 սենյակ"), "Նորք-Մարաշ")
        self.assertEqual(parse_rooms("3-սենյականոց"), 3)
        self.assertEqual(parse_area("92 մ²"), 92.0)
        self.assertEqual(parse_floor("3/12 հարկ"), (3, 12))
        self.assertEqual(parse_features("կենդանիներ թույլատրվում են, BAXI")["pets"], 1)
        self.assertEqual(parse_features("առանց կենդանիների")["pets"], 0)
        self.assertEqual(extract_phone("Զանգ՝ 077 12 34 56"), "+37477123456")
        self.assertEqual(extract_phone("+374 (93) 22-33-44"), "+37493223344")
    def test_hamming(self):
        self.assertEqual(hamming("ff", "fe"), 1)
    def test_landlord(self):
        self.assertEqual(landlord_score("Առանց միջնորդավճար, 650$")[1], "unknown")
        self.assertEqual(landlord_score("Գործակալություն, միջնորդավճար 50%")[1], "agent")
        self.assertEqual(landlord_score("Վարձով, տանտեր")[1], "owner")
        self.assertEqual(landlord_score("Վարձով", listings_with_same_phone=4)[1], "agent")
    def test_price_flag(self):
        items = [dict(district="Կենտրոն", rooms=2, price_usd=p) for p in (600, 620, 650, 700, 680, 250)]
        price_flags(items)
        self.assertEqual(items[-1]["price_flag"], "low"); self.assertIsNone(items[0]["price_flag"])
    def test_ingest_dedupe(self):
        c = get_conn(":memory:")
        a = dict(source="telegram", source_id="x:1", url="u1", images=["f0f0f0f0f0f0f0f0"],
                 text="Կենտրոն, 2 սենյակ, 64 մ², 5/9 հարկ։ 650$։ 077 12 34 56")
        b = dict(source="telegram", source_id="y:9", url="u2", images=["f0f0f0f0f0f0f0f1"],
                 text="Վարձով 2 սենյակ Կենտրոնում 65 մ² 5/9 հարկ 650 դոլար 077-12-34-56")
        d = dict(source="telegram", source_id="z:3", url="u3", images=["0123456789abcdef"],
                 text="Արաբկիր, 3 սենյակ, 92 մ², 3/12 հարկ։ 850$")
        i1, r1 = ingest(c, a); i2, r2 = ingest(c, b); i3, r3 = ingest(c, d)
        self.assertEqual((r1, r2, r3), ("new", "merged", "new"))
        rows = c.execute("SELECT cluster_id FROM listings ORDER BY id").fetchall()
        self.assertEqual(rows[0][0], rows[1][0]); self.assertNotEqual(rows[0][0], rows[2][0])
        self.assertEqual(ingest(c, a)[1], "seen")
        self.assertEqual(ingest(c, dict(source="t", source_id="1", url="u", text="2 սենյակ"))[1], "skipped_no_price")

if __name__ == "__main__":
    unittest.main()
