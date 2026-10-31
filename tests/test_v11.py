"""Contract-version bridge and rights-bound private receipt history (synthetic only)."""
import copy
import json
from pathlib import Path
import unittest
import jsonschema

from eg_productdaten import core
from eg_productdaten import v11
from test_engine import article, catalog, receipt, line, alias, STAMP

ROOT = Path(__file__).parent.parent
SCHEMA11 = json.loads((ROOT / "contracts/v1.1/contract.schema.json").read_text(encoding="utf8"))
SCHEMA10 = json.loads((ROOT / "contracts/v1/contract.schema.json").read_text(encoding="utf8"))
V11 = jsonschema.Draft202012Validator(SCHEMA11, format_checker=jsonschema.FormatChecker())
V10 = jsonschema.Draft202012Validator(SCHEMA10, format_checker=jsonschema.FormatChecker())


class V11AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        jsonschema.Draft202012Validator.check_schema(SCHEMA11)

    def test_explicit_private_paid_observation_validated_v11(self):
        result = v11.historical_purchase_v11(
            receipt(), line(), article(), created_at=STAMP, trace_id="synthetic")
        self.assertIsNone(result["reason"])
        msg = result["message"]
        V11.validate(msg)
        self.assertEqual(msg["contractVersion"], "1.1.0-draft")
        self.assertEqual(msg["meta"]["usageContext"], "PRIVATE_USER_HISTORY")
        self.assertEqual(msg["payload"]["priceKind"], "HISTORICAL_PAID")
        self.assertEqual(msg["payload"]["source"]["evidenceKind"], "USER_CONFIRMED_RECEIPT")
        self.assertTrue(msg["payload"]["egProductdaten"]["notCurrentRetailPrice"])

    def test_existing_v1_stays_independent(self):
        a = core.to_historical_price_observation(receipt(), line(), article())["observation"]
        v1 = core.as_contract("price.observation", a, STAMP, "original")
        V10.validate(v1)
        with self.assertRaises(jsonschema.ValidationError):
            V11.validate(v1)
        v11_msg = v11.historical_purchase_v11(
            receipt(), line(), article(), created_at=STAMP, trace_id="opt-in")["message"]
        with self.assertRaises(jsonschema.ValidationError):
            V10.validate(v11_msg)
        self.assertEqual(v1["contractVersion"], "1.0.0-draft")

    def test_v11_draft_no_unapproved_shopping_producer(self):
        with self.assertRaises(core.InputError):
            v11._envelope("shopping.purchase.suggestion", {}, STAMP, "synthetic", v11.RESEARCH)

    def test_versioned_match_retains_conflicts_and_null_bio(self):
        rows = [article("one", "v1", label="Milch 1 l", organic=None, barcode="4006381333931"),
                article("two", "v1", label="Milch 1 l", organic=None, barcode="00012345678905")]
        for a in rows:
            a["quantity"] = {"amount": 1000, "unit": "ml", "basis": "NET", "confirmed": True}
        original = copy.deepcopy(rows)
        msgs = v11.match_v11(
            {"retailerId": "EDEKA", "rawText": "Milch 1 l"}, rows, [],
            created_at=STAMP, trace_id="m")
        self.assertEqual(len(msgs), 2)
        self.assertTrue(all(m["payload"]["status"] == "AMBIGUOUS" for m in msgs))
        self.assertTrue(all(m["payload"]["candidate"]["organic"] is None for m in msgs))
        self.assertEqual(rows, original)
        for msg in msgs:
            V11.validate(msg)

    def test_private_unconfirmed_ocr_never_price(self):
        msg = v11.receipt_proposal_v11(
            {"lineId": "l", "receiptId": "r", "retailerId": "EDEKA",
             "rawText": "MILCH 199A"}, created_at=STAMP, trace_id="ocr")
        V11.validate(msg)
        self.assertFalse(msg["payload"]["confirmed"])
        self.assertIsNone(msg["payload"]["amountCents"])

    def test_research_only_match_not_public_display(self):
        msg = v11.match_v11({"retailerId": "EDEKA", "gtin": "4006381333931"},
                             catalog(), [], created_at=STAMP, trace_id="test",
                             usage_context=v11.RESEARCH)[0]
        self.assertEqual(msg["meta"]["usageContext"], v11.RESEARCH)
        V11.validate(msg)

    def test_app_display_denied_for_private_receipt(self):
        with self.assertRaises(core.InputError):
            v11.historical_purchase_v11(receipt(), line(), article(),
                                         created_at=STAMP, trace_id="bad",
                                         usage_context="APP_DISPLAY")

    def test_app_display_denied_for_match(self):
        with self.assertRaises(core.InputError):
            v11.match_v11({"retailerId": "EDEKA"}, catalog(), [],
                           created_at=STAMP, trace_id="bad", usage_context="APP_DISPLAY")

    def test_research_denied_for_receipt_ocr(self):
        with self.assertRaises(core.InputError):
            v11.receipt_proposal_v11({"rawText": "private"},
                                     created_at=STAMP, trace_id="bad",
                                     usage_context=v11.RESEARCH)

    def test_research_denied_for_confirmed_private_paid_history(self):
        with self.assertRaises(core.InputError):
            v11.historical_purchase_v11(receipt(), line(), article(),
                                         created_at=STAMP, trace_id="bad",
                                         usage_context=v11.RESEARCH)

    def test_no_arbitrary_external_observation_as_paid(self):
        with self.assertRaises(TypeError):
            v11.historical_purchase_v11(
                {"priceKind": "HISTORICAL_PAID", "priceCents": 100},
                created_at=STAMP, trace_id="bad")

    def test_unconfirmed_purchase_remains_unresolved(self):
        x = v11.historical_purchase_v11(
            receipt(purchaseConfirmed=False), line(), article(),
            created_at=STAMP, trace_id="ocr-unconfirmed")
        self.assertIsNone(x["message"])
        self.assertEqual(x["reason"], "UNCONFIRMED_PURCHASE_OR_LINE")

    def test_wrong_product_version_unresolved(self):
        x = v11.historical_purchase_v11(
            receipt(), line(versionId="v2"), article(),
            created_at=STAMP, trace_id="wrong-version")
        self.assertIsNone(x["message"])
        self.assertEqual(x["reason"], "PRODUCT_VERSION_MISMATCH")

    def test_unallocated_discount_unresolved(self):
        x = v11.historical_purchase_v11(
            receipt(), line(unallocatedDiscount=True), article(),
            created_at=STAMP, trace_id="bad-coupon")
        self.assertIsNone(x["message"])
        self.assertEqual(x["reason"], "UNALLOCATED_DISCOUNT")

    def test_invalid_meta_timestamp_rejected(self):
        with self.assertRaises(core.InputError):
            v11.historical_purchase_v11(receipt(), line(), article(),
                                         created_at="2026-10-31T15:00:00",
                                         trace_id="bad")

    def test_unknown_usage_context_fails_closed(self):
        with self.assertRaises(core.InputError):
            v11.match_v11({"retailerId": "EDEKA"}, catalog(), [],
                           created_at=STAMP, trace_id="x",
                           usage_context="TRUST_ME")


class PrivateHistorySnapshotTests(unittest.TestCase):
    @staticmethod
    def records():
        return [{"receipt": receipt(), "line": line(), "article": article()}]

    def test_dedupe_same_confirmed_line_without_side_effect(self):
        records = self.records()
        original = copy.deepcopy(records)
        result = v11.historical_snapshot_v11(
            records + copy.deepcopy(records), created_at=STAMP,
            trace_id="replay", evidence_cutoff_at=STAMP)
        self.assertEqual(len(result["messages"]), 1)
        self.assertEqual(records, original)
        V11.validate(result["messages"][0])

    def test_two_real_purchases_separate(self):
        records = self.records() + [{
            "receipt": receipt(purchaseId="P-02", receiptId="R-02"),
            "line": line(receiptId="R-02"), "article": article()}]
        result = v11.historical_snapshot_v11(
            records, created_at=STAMP, trace_id="two-real", evidence_cutoff_at=STAMP)
        self.assertEqual(len(result["messages"]), 2)

    def test_hindsight_future_confirmation_invisible(self):
        past = "2026-10-30T10:00:00+01:00"
        result = v11.historical_snapshot_v11(
            self.records(), created_at=STAMP, trace_id="historical",
            evidence_cutoff_at=past)
        self.assertEqual(result["messages"], [])

    def test_unconfirmed_draft_not_in_memory(self):
        records = self.records()
        records[0]["receipt"]["purchaseConfirmed"] = False
        result = v11.historical_snapshot_v11(
            records, created_at=STAMP, trace_id="draft", evidence_cutoff_at=STAMP)
        self.assertFalse(result["messages"])
        self.assertEqual(result["unresolved"][0]["reason"], "UNCONFIRMED_PURCHASE_OR_LINE")

    def test_conflicting_same_purchase_price_raises(self):
        records = self.records()
        other = copy.deepcopy(records[0])
        other["line"]["amountCents"] = 450
        with self.assertRaises(core.ConflictError):
            v11.historical_snapshot_v11(
                records+[other], created_at=STAMP,
                trace_id="conflict", evidence_cutoff_at=STAMP)

    def test_missing_evidence_cutoff_zone_rejected(self):
        with self.assertRaises(core.InputError):
            v11.historical_snapshot_v11(
                self.records(), created_at=STAMP, trace_id="bad",
                evidence_cutoff_at="2026-10-31T15:00:00")

    def test_missing_purchase_line_is_invalid(self):
        with self.assertRaises(core.InputError):
            v11.historical_snapshot_v11(
                [{"receipt":receipt()}], created_at=STAMP,
                trace_id="bad", evidence_cutoff_at=STAMP)


if __name__ == "__main__":
    unittest.main()
