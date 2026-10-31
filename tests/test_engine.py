"""Synthetic-only regression and Architecture v1 contract tests."""
import copy
import json
from pathlib import Path
import unittest

from eg_productdaten import core as p

STAMP = "2026-10-31T15:00:00+01:00"


def article(id="edeka-oats", version="v1", retailer="EDEKA", label="GUT & GÜNSTIG Haferflocken 500 g",
            barcode="4006381333931", brand="GUT & GÜNSTIG", organic=False, amount=500,
            package_count=1, sku="ED-001"):
    return {
        "id": id, "versionId": version, "retailerId": retailer, "label": label,
        "gtin": barcode, "retailerArticleId": sku, "brandName": brand, "organic": organic,
        "foodTypeId": "fine-oats", "attributes": {"form": "fine"},
        "currentVersionConfirmed": True,
        "quantity": {"amount": amount, "unit": "g", "basis": "NET",
                     "confirmed": True, "packageCount": package_count}
    }


def catalog():
    return [
        article(),
        article("edeka-bio", "v2", "EDEKA", "EDEKA BIO Haferflocken 500 g",
                "00012345678905", "EDEKA BIO", True, sku="ED-002"),
        article("netto-bio", "v1", "NETTO_MARKEN_DISCOUNT", "BIOBIO Haferflocken 500 g",
                "96385074", "BIOBIO", True, sku="ND-002"),
        article("penny-bio", "v1", "PENNY", "NATURGUT Haferflocken 500 g",
                "036000291452", "NATURGUT", True, sku="PY-003"),
        article("milk1", "m1", "EDEKA", "Milch 1 l", "00123456789012", None, None,
                1000, sku="ED-M1"),
    ]


def receipt(**kw):
    r = dict(purchaseId="P-01", receiptId="R-01", retailerId="EDEKA", storeId="E-123",
             purchaseAt="2026-10-29T19:05:00+01:00", confirmedAt=STAMP,
             purchaseConfirmed=True)
    r.update(kw)
    return r


def line(**kw):
    l = dict(lineId="L-01", receiptId="R-01", retailerId="EDEKA", productId="edeka-oats",
             versionId="v1", lineKind="FOOD", confirmed=True, productConfirmed=True,
             unitsConfirmed=True, purchaseUnits=1, amountCents=199, discountReconciled=True,
             amountExcludesDeposit=True)
    l.update(kw)
    return l


def alias(action="CONFIRM", **kw):
    x = dict(decisionId="A-1", retailerId="EDEKA", rawText="HAFERFL ZART 0,89",
             productId="edeka-oats", versionId="v1", confirmed=True, action=action,
             reason="synthetic manual verification", decidedAt=STAMP, expectedPreviousId=None)
    x.update(kw)
    return x


class GtinTests(unittest.TestCase):
    def test_ean8(self):
        self.assertEqual(p.normalize_gtin("96385074"), "96385074")

    def test_upc12_leading_zero(self):
        self.assertEqual(p.normalize_gtin("036000291452"), "036000291452")

    def test_ean13(self):
        self.assertEqual(p.normalize_gtin("4006381333931"), "4006381333931")

    def test_gtin14_leading_zeros(self):
        self.assertEqual(p.normalize_gtin("00012345678905"), "00012345678905")

    def test_gtin_padded_lookup_compatible_with_android(self):
        self.assertEqual(p.gtin_lookup_key("036000291452"), p.gtin_lookup_key("0036000291452"))

    def test_all_zero_rejected(self):
        with self.assertRaises(p.InputError):
            p.normalize_gtin("00000000")

    def test_bad_check_digit(self):
        with self.assertRaises(p.InputError):
            p.normalize_gtin("4006381333932")

    def test_reject_sku_as_gtin(self):
        with self.assertRaises(p.InputError):
            p.normalize_gtin("ED-001")

    def test_reject_whitespace_unicode_and_int(self):
        for value in (" 96385074", "９６３８５０７４", 96385074, "0000000O00000"):
            with self.subTest(value=value), self.assertRaises(p.InputError):
                p.normalize_gtin(value)


class ProductTests(unittest.TestCase):
    def test_brand_mapping_edeka_netto_penny(self):
        for retailer, brand in [("EDEKA", "GUT & GÜNSTIG"),
                                ("NETTO_MARKEN_DISCOUNT", "BIOBIO"),
                                ("PENNY", "NATURGUT")]:
            with self.subTest(retailer=retailer):
                self.assertEqual(p.infer_brand_kind(brand, retailer), "PRIVATE_LABEL")

    def test_scottie_netto_is_distinct(self):
        self.assertEqual(p.infer_brand_kind("BIOBIO", "NETTO_MIT_SCOTTIE"), "UNKNOWN")

    def test_no_organic_inference_from_no_bio(self):
        a = article(organic=None)
        self.assertIsNone(p.normalize_article(a)["organic"])

    def test_unknown_brand_unknown_kind(self):
        a = article(brand="Unknown Synthetic Brand", organic=None)
        self.assertEqual(p.normalize_article(a)["brandKind"], "UNKNOWN")

    def test_import_provenance(self):
        x = p.normalize_article(article(), {"origin": "synthetic",
                                             "rightsStatus": "UNVERIFIED", "dataQuality": "SOURCED"})
        self.assertEqual(x["importSource"]["rightsStatus"], "UNVERIFIED")

    def test_import_invalid_source(self):
        with self.assertRaises(p.InputError):
            p.normalize_article(article(), {"origin": "synthetic", "rightsStatus": "PERHAPS"})

    def test_missing_version(self):
        with self.assertRaises(p.InputError):
            p.normalize_article({**article(), "versionId": None})

    def test_organic_is_not_boolean_cast(self):
        with self.assertRaises(p.InputError):
            p.normalize_article({**article(), "organic": "false"})

    def test_exact_gtin_without_confirmation(self):
        out = p.find_candidates({"retailerId": "EDEKA", "gtin": "4006381333931", "requestId": "X"},
                                catalog())
        found = next(x for x in out if x["egProductdaten"]["productId"] == "edeka-oats")
        self.assertEqual(found["matchLevel"], "EXACT_SKU")
        self.assertEqual(found["status"], "SUGGESTED")
        self.assertTrue(found["egProductdaten"]["requiresPurchaseConfirmation"])

    def test_exact_retailer_sku(self):
        out = p.find_candidates({"retailerId": "EDEKA", "retailerArticleId": "ED-001"}, catalog())
        self.assertEqual(out[0]["egProductdaten"]["productId"], "edeka-oats")
        self.assertIn("retailer_sku_exact", out[0]["evidence"])

    def test_sku_different_retailer_not_exact(self):
        out = p.find_candidates({"retailerId": "PENNY", "retailerArticleId": "ED-001"}, catalog())
        self.assertFalse(any("retailer_sku_exact" in x["evidence"] for x in out))

    def test_bad_gtin_stops_matching(self):
        with self.assertRaises(p.InputError):
            p.find_candidates({"retailerId": "EDEKA", "gtin": "4006381333932"}, catalog())

    def test_two_plausible_candidates_ambiguous(self):
        rows = [article("a", "v1", label="Milch 1 l", barcode="4006381333931", sku="a"),
                article("b", "v1", label="Milch 1 l", barcode="00012345678905", sku="b")]
        for row in rows:
            row["quantity"] = {"amount": 1000, "unit": "ml", "basis": "NET",
                               "confirmed": True, "packageCount": 1}
        out = p.find_candidates({"retailerId": "EDEKA", "rawText": "MILCH 1L"}, rows)
        self.assertEqual(sum(x["status"] == "AMBIGUOUS" for x in out), 2)

    def test_similar_wrong_package_rejected(self):
        a = article(amount=500)
        matches = p.find_candidates({"retailerId": "EDEKA", "rawText": "Haferflocken 1 kg"}, [a])
        self.assertIn("package_or_unit_conflict", matches[0]["conflicts"])
        self.assertEqual(matches[0]["status"], "REJECTED")

    def test_multipack_conflict(self):
        a = article(package_count=2)
        out = p.find_candidates({"retailerId": "EDEKA", "rawText": "1x500g Haferflocken"}, [a])
        self.assertEqual(out[0]["status"], "REJECTED")

    def test_multipack_match(self):
        a = article(package_count=2)
        out = p.find_candidates({"retailerId": "EDEKA", "rawText": "2x500g Haferflocken"}, [a])
        self.assertIn("confirmed_package_agrees", out[0]["evidence"])

    def test_bio_conflict(self):
        out = p.find_candidates({"retailerId": "EDEKA", "rawText": "BIO Haferflocken 500g"},
                                [article(organic=False)])
        self.assertEqual(out[0]["status"], "REJECTED")

    def test_bio_unknown_not_false(self):
        out = p.find_candidates({"retailerId": "EDEKA", "rawText": "BIO Haferflocken 500g"},
                                [article(organic=None)])
        self.assertNotIn("explicit_bio_conflict", out[0]["conflicts"])

    def test_duplicate_gtin_versions_not_auto_winner(self):
        a = article()
        b = article("same-code-different-product", "v2")
        out = p.find_candidates({"retailerId": "EDEKA", "gtin": "4006381333931"}, [a, b])
        self.assertEqual(sum(x["status"] == "AMBIGUOUS" for x in out), 2)

    def test_no_candidate(self):
        self.assertEqual(p.find_candidates({"retailerId": "EDEKA", "rawText": "UNRELATED"},
                                           [article()]), [])

    def test_five_typical_synthetic_product_cases(self):
        fixtures = [
            ("EDEKA", "ED-001", "edeka-oats"),
            ("EDEKA", "ED-002", "edeka-bio"),
            ("NETTO_MARKEN_DISCOUNT", "ND-002", "netto-bio"),
            ("PENNY", "PY-003", "penny-bio"),
            ("EDEKA", "ED-M1", "milk1")
        ]
        for retail, sku, expected in fixtures:
            with self.subTest(sku=sku):
                out = p.find_candidates({"retailerId": retail, "retailerArticleId": sku}, catalog())
                self.assertEqual(out[0]["egProductdaten"]["productId"], expected)



class OfflineImportTests(unittest.TestCase):
    @staticmethod
    def source():
        return {"origin": "OpenFoodFacts fixture", "observedAt": STAMP,
                "rightsStatus": "UNVERIFIED", "dataQuality": "SOURCED"}

    def test_off_snapshot_yields_unconfirmed_product(self):
        x = p.import_off_snapshot({"code": "4006381333931",
                                   "product": {"product_name_de": "Bio Haferflocken",
                                               "brands": "GUT & GÜNSTIG",
                                               "labels_tags": ["en:organic"],
                                               "quantity": "2x500 g"}},
                                  "offline-1", "v1", "EDEKA", self.source())
        self.assertEqual(x["gtin"], "4006381333931")
        self.assertEqual(x["brandKind"], "PRIVATE_LABEL")
        self.assertTrue(x["organic"])
        self.assertEqual(x["quantity"]["amount"], 500)
        self.assertEqual(x["quantity"]["packageCount"], 2)
        self.assertEqual(x["quantity"]["basis"], "UNKNOWN")
        self.assertFalse(x["quantity"]["confirmed"])
        self.assertEqual(x["importSource"]["rightsStatus"], "UNVERIFIED")

    def test_off_no_bio_label_does_not_mean_nonorganic(self):
        x = p.import_off_snapshot({"product_name": "Mystery Oat Product",
                                   "brands": "Unfamiliar brand", "quantity": "1 kg"},
                                  "offline-2", "v1", None, self.source())
        self.assertIsNone(x["organic"])
        self.assertEqual(x["quantity"]["amount"], 1000)
        self.assertEqual(x["quantity"]["unit"], "g")

    def test_off_no_net_or_drained_assumption(self):
        x = p.import_off_snapshot({"product_name": "Beans", "quantity": "240 g"},
                                  "offline-3", "v1", None, self.source())
        self.assertEqual(x["quantity"]["basis"], "UNKNOWN")

    def test_off_conflicting_barcode_rejected(self):
        with self.assertRaises(p.InputError):
            p.import_off_snapshot({"code": "4006381333931", "product":
                                  {"code": "00012345678905", "product_name": "Oats"}},
                                  "offline-4", "v1", None, self.source())

    def test_off_invalid_barcode_rejected(self):
        with self.assertRaises(p.InputError):
            p.import_off_snapshot({"product_name": "Oats", "code": "4006381333932"},
                                  "offline-5", "v1", None, self.source())

    def test_off_no_provenance_rejected(self):
        with self.assertRaises(p.InputError):
            p.import_off_snapshot({"product_name": "Oats"}, "offline-6", "v1")

    def test_off_cannot_fake_user_confirmation(self):
        with self.assertRaises(p.InputError):
            p.import_off_snapshot({"product_name": "Oats"}, "offline-7", "v1", source={
                "origin": "OpenFoodFacts", "observedAt": STAMP,
                "rightsStatus": "UNVERIFIED", "dataQuality": "CONFIRMED"})

    def test_off_absent_name_rejected(self):
        with self.assertRaises(p.InputError):
            p.import_off_snapshot({"product": {"code": "4006381333931"}},
                                  "offline-8", "v1", None, self.source())



class AliasTests(unittest.TestCase):
    def test_explicit_confirmation_and_replay(self):
        a = alias()
        ledger = p.resolve_alias_decision([], a)
        self.assertEqual(ledger, p.resolve_alias_decision(ledger, a))
        self.assertEqual(len(ledger), 1)

    def test_no_confirmed_flag(self):
        with self.assertRaises(p.InputError):
            p.resolve_alias_decision([], alias(confirmed=False))

    def test_same_text_other_retailer_not_reused(self):
        ledger = p.resolve_alias_decision([], alias())
        out = p.find_candidates({"retailerId": "PENNY", "rawText": "HAFERFL ZART 0,89"},
                                [article()], ledger)
        self.assertFalse(any("user_confirmed_retailer_alias_version" in x["evidence"] for x in out))

    def test_confirmed_alias_current_version(self):
        ledger = p.resolve_alias_decision([], alias())
        out = p.find_candidates({"retailerId": "EDEKA", "rawText": "HAFERFL ZART 0,89"},
                                [article()], ledger)
        self.assertEqual(out[0]["status"], "CONFIRMED_BY_USER")
        self.assertEqual(out[0]["egProductdaten"]["versionId"], "v1")

    def test_stale_alias_when_both_versions_in_catalog(self):
        ledger = p.resolve_alias_decision([], alias())
        older = article(version="v1")
        older["currentVersionConfirmed"] = False
        newer = article(version="v2")
        out = p.find_candidates({"retailerId": "EDEKA", "rawText": "HAFERFL ZART 0,89"},
                                [older, newer], ledger)
        self.assertFalse(any(x["status"] == "CONFIRMED_BY_USER" for x in out))

    def test_alias_version_unverified_rejected_as_autoconfirmation(self):
        ledger = p.resolve_alias_decision([], alias())
        a = article()
        del a["currentVersionConfirmed"]
        out = p.find_candidates({"retailerId": "EDEKA", "rawText": "HAFERFL ZART 0,89"},
                                [a], ledger)
        self.assertEqual(out[0]["status"], "AMBIGUOUS")
        self.assertIn("current_product_version_not_confirmed", out[0]["conflicts"])

    def test_same_version_id_different_product_never_inherits_alias(self):
        ledger = p.resolve_alias_decision([], alias())
        rows = [article(), article("other-food", "v1", label="HAFERFL ZART", sku="EXTRA")]
        out = p.find_candidates({"retailerId": "EDEKA", "rawText": "HAFERFL ZART 0,89"},
                                rows, ledger)
        confirmed = [x for x in out if "user_confirmed_retailer_alias_version" in x["evidence"]]
        self.assertEqual(len(confirmed), 1)
        self.assertEqual(confirmed[0]["egProductdaten"]["productId"], "edeka-oats")

    def test_stale_alias_version_no_spurious_match(self):
        ledger = p.resolve_alias_decision([], alias())
        changed = article(version="v2")
        out = p.find_candidates({"retailerId": "EDEKA", "rawText": "HAFERFL ZART 0,89"},
                                [changed], ledger)
        self.assertFalse(any("user_confirmed_retailer_alias_version" in x["evidence"] for x in out))

    def test_revoke_alias(self):
        ledger = p.resolve_alias_decision([], alias())
        ledger = p.resolve_alias_decision(ledger, alias("REVOKE", decisionId="A-2",
                                                        expectedPreviousId="A-1"))
        out = p.find_candidates({"retailerId": "EDEKA", "rawText": "HAFERFL ZART 0,89"},
                                [article()], ledger)
        self.assertFalse(any(x["status"] == "CONFIRMED_BY_USER" for x in out))

    def test_correct_alias_version(self):
        ledger = p.resolve_alias_decision([], alias())
        ledger = p.resolve_alias_decision(ledger, alias("CORRECT", decisionId="A-2",
                                                        expectedPreviousId="A-1",
                                                        productId="edeka-bio", versionId="v2"))
        out = p.find_candidates({"retailerId": "EDEKA", "rawText": "HAFERFL ZART 0,89"},
                                catalog(), ledger)
        confirmed = [x for x in out if "user_confirmed_retailer_alias_version" in x["evidence"]]
        self.assertEqual(len(confirmed), 1)
        self.assertEqual(confirmed[0]["egProductdaten"]["versionId"], "v2")

    def test_stale_cas(self):
        ledger = p.resolve_alias_decision([], alias())
        with self.assertRaises(p.ConflictError):
            p.resolve_alias_decision(ledger, alias("CORRECT", decisionId="A-2",
                                                    expectedPreviousId=None))
    
    def test_replay_changed_payload_conflict(self):
        ledger = p.resolve_alias_decision([], alias())
        with self.assertRaises(p.ConflictError):
            p.resolve_alias_decision(ledger, alias(reason="changed evidence"))

    def test_ambiguous_legacy_ledger_blocks_silent_choice(self):
        a = alias()
        b = alias(decisionId="A-2", versionId="v2")
        with self.assertRaises(p.ConflictError):
            p.resolve_alias_decision([a, b], alias("CORRECT", decisionId="A-3"))


class ReceiptTests(unittest.TestCase):
    def test_five_typical_line_cases(self):
        cases = [("Haferflocken 1,99", "UNKNOWN", 199),
                 ("Pfand 0,25", "DEPOSIT", 25),
                 ("Rabatt 0,50", "DISCOUNT", 50),
                 ("TASCHE 0,20", "NON_FOOD", 20),
                 ("Retoure 2,99", "RETURN", 299)]
        for raw, kind, cents in cases:
            with self.subTest(raw=raw):
                x = p.classify_receipt_line({"rawText": raw})
                self.assertEqual((x["lineKind"], x["amountCents"]), (kind, cents))
                self.assertEqual(x["rawText"], raw)
                self.assertFalse(x["confirmed"])

    def test_five_difficult_line_cases(self):
        cases = [("Milch 199A", "UNKNOWN", None),
                 ("RÜCKGELD 1,20", "UNKNOWN", 120),
                 ("STORNO 1,49", "RETURN", 149),
                 ("UNBEKANNT", "UNKNOWN", None),
                 ("MILCH 1.99", "UNKNOWN", 199)]
        for raw, kind, cents in cases:
            with self.subTest(raw=raw):
                x = p.classify_receipt_line({"rawText": raw})
                self.assertEqual((x["lineKind"], x["amountCents"]), (kind, cents))

    def test_negative_amount_unknown_not_food(self):
        x = p.classify_receipt_line({"rawText": "MILCH", "lineKind": "FOOD", "amountCents": -120})
        self.assertEqual(x["lineKind"], "UNKNOWN")

    def test_zero_not_null(self):
        x = p.classify_receipt_line({"rawText": "Pfand", "amountCents": 0})
        self.assertEqual(x["amountCents"], 0)

    def test_float_forbidden(self):
        with self.assertRaises(p.InputError):
            p.classify_receipt_line({"rawText": "MILCH", "amountCents": 1.99})

    def test_receipt_line_contract_preserves_raw(self):
        x = p.classify_receipt_line({"rawText": "BIO HAFER 1,99", "lineId": "L", "receiptId": "R",
                                     "retailerId": "EDEKA", "confirmed": False})
        self.assertEqual(x["rawText"], "BIO HAFER 1,99")
        self.assertIsNone(x["linkedArticle"])


class PriceTests(unittest.TestCase):
    def test_confirmed_exactly_one(self):
        result = p.to_historical_price_observation(receipt(), line(), article())
        obs = result["observation"]
        self.assertIsNone(result["reason"])
        self.assertEqual(obs["priceCents"], 199)
        self.assertEqual(obs["priceKind"], "HISTORICAL_PAID")
        self.assertEqual(obs["scope"]["scopeType"], "STORE_CONFIRMED")
        self.assertEqual(obs["egProductdaten"]["purchaseAt"], receipt()["purchaseAt"])
        self.assertNotIn("validCurrentPrice", obs)

    def test_unconfirmed_purchase(self):
        x = p.to_historical_price_observation(receipt(purchaseConfirmed=False), line(), article())
        self.assertIsNone(x["observation"])

    def test_unconfirmed_line(self):
        x = p.to_historical_price_observation(receipt(), line(confirmed=False), article())
        self.assertIsNone(x["observation"])

    def test_unconfirmed_link(self):
        x = p.to_historical_price_observation(receipt(), line(productConfirmed=False), article())
        self.assertIsNone(x["observation"])

    def test_ocr_only_no_price(self):
        x = p.to_historical_price_observation(receipt(), line(amountCents=None), article())
        self.assertEqual(x["reason"], "UNKNOWN_OR_INVALID_PRICE")

    def test_no_date(self):
        x = p.to_historical_price_observation(receipt(purchaseAt=None), line(), article())
        self.assertEqual(x["reason"], "MISSING_PURCHASE_DATE")

    def test_app_only_confirmed_purchase_date_no_time_invented(self):
        x = p.to_historical_price_observation(receipt(purchaseAt=None, purchasedOn="2026-10-29"),
                                                line(), article())
        self.assertIsNone(x["reason"])
        self.assertIsNone(x["observation"]["egProductdaten"]["purchaseAt"])
        self.assertEqual(x["observation"]["egProductdaten"]["purchasedOn"], "2026-10-29")

    def test_purchase_day_conflict(self):
        x = p.to_historical_price_observation(receipt(purchasedOn="2026-10-28"), line(), article())
        self.assertEqual(x["reason"], "PURCHASE_DATE_CONFLICT")

    def test_timezone_naive_rejected(self):
        x = p.to_historical_price_observation(receipt(purchaseAt="2026-10-29T19:05:00"), line(), article())
        self.assertEqual(x["reason"], "INVALID_DATE_OR_ARTICLE")

    def test_no_store_cannot_claim_store_confirmed(self):
        x = p.to_historical_price_observation(receipt(storeId=None), line(), article())
        self.assertEqual(x["observation"]["scope"]["scopeType"], "UNKNOWN")

    def test_multi_pack_paid_per_unit(self):
        x = p.to_historical_price_observation(receipt(), line(amountCents=398, purchaseUnits=2), article())
        self.assertEqual(x["observation"]["priceCents"], 199)

    def test_indivisible_price_keeps_unknown(self):
        x = p.to_historical_price_observation(receipt(), line(amountCents=100, purchaseUnits=3), article())
        self.assertEqual(x["reason"], "NONINTEGRAL_UNIT_PRICE")

    def test_wrong_version(self):
        x = p.to_historical_price_observation(receipt(), line(versionId="v2"), article())
        self.assertEqual(x["reason"], "PRODUCT_VERSION_MISMATCH")

    def test_wrong_barcode(self):
        x = p.to_historical_price_observation(receipt(), line(gtin="00012345678905"), article())
        self.assertEqual(x["reason"], "BARCODE_CONFLICT")

    def test_wrong_retailer(self):
        x = p.to_historical_price_observation(receipt(), line(retailerId="PENNY"), article())
        self.assertEqual(x["reason"], "MERCHANT_MISMATCH")

    def test_discount_allocation(self):
        x = p.to_historical_price_observation(receipt(),
                     line(amountCents=500, allocatedDiscountCents=100, discountApplied=True,
                          purchaseUnits=2), article())
        self.assertEqual(x["observation"]["priceCents"], 200)

    def test_unallocated_discount(self):
        x = p.to_historical_price_observation(receipt(), line(unallocatedDiscount=True), article())
        self.assertEqual(x["reason"], "UNALLOCATED_DISCOUNT")

    def test_discount_unclear(self):
        x = p.to_historical_price_observation(receipt(), line(discountReconciled=False), article())
        self.assertEqual(x["reason"], "DISCOUNT_ACCOUNTING_UNKNOWN")

    def test_deposit_unclear(self):
        x = p.to_historical_price_observation(receipt(), line(amountExcludesDeposit=False), article())
        self.assertEqual(x["reason"], "DEPOSIT_ACCOUNTING_UNKNOWN")

    def test_deposit_separate(self):
        x = p.to_historical_price_observation(receipt(), line(depositPerUnitCents=25), article())
        self.assertEqual(x["observation"]["depositCents"], 25)
        self.assertEqual(x["observation"]["priceCents"], 199)

    def test_retur_and_discount_not_food(self):
        for kind in ("RETURN", "DISCOUNT", "DEPOSIT", "NON_FOOD", "UNKNOWN"):
            with self.subTest(kind=kind):
                x = p.to_historical_price_observation(receipt(), line(lineKind=kind), article())
                self.assertIsNone(x["observation"])

    def test_zero_paid_price_not_unknown(self):
        x = p.to_historical_price_observation(receipt(), line(amountCents=0), article())
        self.assertEqual(x["observation"]["priceCents"], 0)

    def test_dup_scan_retry_single_observation(self):
        record = {"receipt": receipt(), "line": line(), "article": article()}
        mem = p.build_price_memory([record, copy.deepcopy(record), copy.deepcopy(record)])
        self.assertEqual(len(mem["observations"]), 1)

    def test_two_real_identical_purchases_distinct(self):
        r1 = {"receipt": receipt(), "line": line(), "article": article()}
        r2 = {"receipt": receipt(purchaseId="P-02", receiptId="R-02"),
              "line": line(receiptId="R-02"), "article": article()}
        mem = p.build_price_memory([r1, r2])
        self.assertEqual(len(mem["observations"]), 2)

    def test_conflicting_retry_requires_review(self):
        r1 = {"receipt": receipt(), "line": line(), "article": article()}
        r2 = {"receipt": receipt(), "line": line(amountCents=249), "article": article()}
        with self.assertRaises(p.ConflictError):
            p.build_price_memory([r1, r2])

    def test_retract_with_revision_and_idempotence(self):
        obs = p.to_historical_price_observation(receipt(), line(), article())["observation"]
        oid = obs["observationId"]
        state = {"entries": {oid: {"revision": 1, "observation": obs}}, "events": {}}
        event = {"eventId": "e1", "observationId": oid, "action": "RETRACT", "confirmed": True,
                 "expectedRevision": 1, "decidedAt": STAMP}
        newer = p.apply_memory_correction(state, event)
        self.assertIsNone(newer["entries"][oid]["observation"])
        self.assertIsNotNone(state["entries"][oid]["observation"])
        self.assertEqual(p.apply_memory_correction(newer, event), newer)
        with self.assertRaises(p.ConflictError):
            p.apply_memory_correction(newer, {**event, "eventId": "e2"})

    def test_correct_link_with_confirmed_replacement(self):
        obs = p.to_historical_price_observation(receipt(), line(), article())["observation"]
        oid = obs["observationId"]
        corrected_article = article(label="corrected synthetic label")
        event = {"eventId": "e1", "observationId": oid, "action": "REPLACE", "confirmed": True,
                 "expectedRevision": 1, "decidedAt": STAMP, "receipt": receipt(),
                 "line": line(), "article": corrected_article}
        newer = p.apply_memory_correction(
            {"entries": {oid: {"revision": 1, "observation": obs}}, "events": {}}, event)
        self.assertEqual(newer["entries"][oid]["revision"], 2)

    def test_correction_rejects_raw_unverified_replacement(self):
        obs = p.to_historical_price_observation(receipt(), line(), article())["observation"]
        oid = obs["observationId"]
        state = {"entries": {oid: {"revision": 1, "observation": obs}}, "events": {}}
        forged = copy.deepcopy(obs)
        forged["priceCents"] = 0
        event = {"eventId": "forged", "observationId": oid, "action": "REPLACE",
                 "confirmed": True, "expectedRevision": 1, "decidedAt": STAMP,
                 "replacement": forged}
        with self.assertRaises(p.InputError):
            p.apply_memory_correction(state, event)

    def test_correction_rejects_unconfirmed_purchase(self):
        obs = p.to_historical_price_observation(receipt(), line(), article())["observation"]
        oid = obs["observationId"]
        state = {"entries": {oid: {"revision": 1, "observation": obs}}, "events": {}}
        event = {"eventId": "bad", "observationId": oid, "action": "REPLACE",
                 "confirmed": True, "expectedRevision": 1, "decidedAt": STAMP,
                 "receipt": receipt(purchaseConfirmed=False), "line": line(),
                 "article": article()}
        with self.assertRaises(p.InputError):
            p.apply_memory_correction(state, event)

    def test_correction_rejects_different_line(self):
        obs = p.to_historical_price_observation(receipt(), line(), article())["observation"]
        oid = obs["observationId"]
        state = {"entries": {oid: {"revision": 1, "observation": obs}}, "events": {}}
        event = {"eventId": "bad2", "observationId": oid, "action": "REPLACE",
                 "confirmed": True, "expectedRevision": 1, "decidedAt": STAMP,
                 "receipt": receipt(), "line": line(lineId="other"), "article": article()}
        with self.assertRaises(p.ConflictError):
            p.apply_memory_correction(state, event)

    def test_correction_rejects_forged_payload_mismatch(self):
        obs = p.to_historical_price_observation(receipt(), line(), article())["observation"]
        oid = obs["observationId"]
        state = {"entries": {oid: {"revision": 1, "observation": obs}}, "events": {}}
        forged = copy.deepcopy(obs)
        forged["priceCents"] = 0
        event = {"eventId": "bad3", "observationId": oid, "action": "REPLACE",
                 "confirmed": True, "expectedRevision": 1, "decidedAt": STAMP,
                 "receipt": receipt(), "line": line(), "article": article(), "replacement": forged}
        with self.assertRaises(p.ConflictError):
            p.apply_memory_correction(state, event)

    def test_confirmation_cannot_precede_purchase(self):
        r = receipt(confirmedAt="2026-10-28T19:05:00+01:00")
        result = p.to_historical_price_observation(r, line(), article())
        self.assertEqual(result["reason"], "CONFIRMATION_PRECEDES_PURCHASE")

    def test_confirmed_day_cannot_precede_known_purchase_day(self):
        r = receipt(confirmedAt="2026-10-28T19:05:00+01:00", purchaseAt=None, purchasedOn="2026-10-29")
        result = p.to_historical_price_observation(r, line(), article())
        self.assertEqual(result["reason"], "CONFIRMATION_PRECEDES_PURCHASE")

    def test_memory_builder_pure(self):
        x = {"receipt": receipt(), "line": line(), "article": article()}
        before = copy.deepcopy(x)
        p.build_price_memory([x])
        self.assertEqual(x, before)


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import jsonschema
        cls.js = jsonschema
        cls.schema = json.loads((Path(__file__).parent.parent / "contracts" / "v1" /
                                 "contract.schema.json").read_text(encoding="utf-8"))

    def validate(self, type_, payload):
        msg = p.as_contract(type_, payload, STAMP, "synthetic")
        self.js.Draft202012Validator(self.schema,
                format_checker=self.js.FormatChecker()).validate(msg)
        return msg

    def test_match_contract(self):
        out = p.find_candidates({"retailerId": "EDEKA", "gtin": "4006381333931"}, catalog())
        self.validate("product.match", out[0])

    def test_receipt_contract(self):
        out = p.classify_receipt_line({"rawText": "Haferflocken 1,99",
                                        "lineId": "L", "receiptId": "R", "retailerId": "EDEKA"})
        self.validate("receipt.line", out)

    def test_observation_contract(self):
        out = p.to_historical_price_observation(receipt(), line(), article())["observation"]
        self.validate("price.observation", out)

    def test_null_and_zero_contract(self):
        obs = p.to_historical_price_observation(receipt(storeId=None), line(amountCents=0),
                                                  article(organic=None))["observation"]
        self.validate("price.observation", obs)
        self.assertIsNone(obs["article"]["organic"])
        self.assertEqual(obs["priceCents"], 0)

    def test_bad_payload_rejected_formally(self):
        msg = p.as_contract("price.observation",
                            p.to_historical_price_observation(receipt(), line(), article())["observation"],
                            STAMP, "bad")
        msg["payload"]["priceCents"] = 1.99
        with self.assertRaises(self.js.ValidationError):
            self.js.Draft202012Validator(self.schema).validate(msg)

    def test_unknown_missing_required_rejected(self):
        msg = self.validate("product.match",
                            p.find_candidates({"retailerId": "EDEKA", "gtin": "4006381333931"}, catalog())[0])
        del msg["payload"]["status"]
        with self.assertRaises(self.js.ValidationError):
            self.js.Draft202012Validator(self.schema).validate(msg)


if __name__ == "__main__":
    unittest.main()
