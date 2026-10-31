"""Offline product identity and receipt-price decision engine.

Pure functions; input and output are JSON-compatible dicts. No IO, network,
camera, OCR, database, clock, or app purchase side effects.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re
import unicodedata

CONTRACT_VERSION = "1.0.0-draft"
BRAND_KINDS = {"MANUFACTURER", "PRIVATE_LABEL", "UNKNOWN"}
LINE_KINDS = {"FOOD", "NON_FOOD", "DEPOSIT", "DISCOUNT", "RETURN", "UNKNOWN"}
PRIVATE_LABELS = {
    "EDEKA": {"GUT & GÜNSTIG", "EDEKA BIO", "EDEKA HERZSTÜCKE"},
    "NETTO_MARKEN_DISCOUNT": {"BIOBIO", "GUT PONHOLZ"},
    "PENNY": {"NATURGUT", "PENNY"},
}
_PACK = re.compile(r"(?<!\w)(?:(\d+)\s*[x×]\s*)?(\d+(?:[.,]\d+)?)\s*(kg|ml|g|l)(?!\w)", re.I)
_PRICE = re.compile(r"(?<![0-9.,])([+-]?\d+[,.]\d{2})\s*(?:€|EUR)?\s*(?:[A-D])?\s*$", re.I)
_TOKENS = re.compile(r"[a-z0-9äöüß]+", re.I)


class InputError(ValueError):
    """Malformed or insufficient trusted inputs."""


class ConflictError(ValueError):
    """Concurrent/history conflict; never silently last-write-wins."""


def _text(value):
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).casefold().split())


def _key(value):
    return _text(value).upper()


def _int(value, field, minimum=None):
    if type(value) is not int or (minimum is not None and value < minimum):
        raise InputError(f"{field}: expected integer" + (f" >= {minimum}" if minimum is not None else ""))
    return value


def _timestamp(value, field):
    if not isinstance(value, str):
        raise InputError(f"{field}: timezone-aware ISO-8601 required")
    try:
        d = datetime.fromisoformat(value)
        if d.utcoffset() is None:
            raise ValueError("missing timezone")
        return d
    except ValueError as exc:
        raise InputError(f"{field}: timezone-aware ISO-8601 required") from exc


def normalize_gtin(code):
    """GTIN 8/12/13/14, ASCII digits only; keep length and leading zeros."""
    if not isinstance(code, str) or not re.fullmatch(r"[0-9]{8}|[0-9]{12}|[0-9]{13}|[0-9]{14}", code):
        raise InputError("Invalid GTIN length or characters")
    if not any(x != "0" for x in code):
        raise InputError("All-zero GTIN is not a product identifier")
    digits = [int(x) for x in code]
    check = (10 - sum(d * (3 if i % 2 == 0 else 1)
                      for i, d in enumerate(reversed(digits[:-1]))) % 10) % 10
    if check != digits[-1]:
        raise InputError("Invalid GTIN check digit")
    return code


def gtin_lookup_key(code):
    """The existing Android reader compares the zero-padded 14-digit key."""
    return normalize_gtin(code).zfill(14)


def infer_brand_kind(brand_name, retailer_id):
    """Conservative reviewed brand names; never infer organic status."""
    if _key(brand_name) in PRIVATE_LABELS.get(_key(retailer_id), set()):
        return "PRIVATE_LABEL"
    return "UNKNOWN"


def _pack(value):
    """Return evidenced (package count or None, per-pack amount, unit)."""
    if not value:
        return None
    m = _PACK.search(str(value))
    if not m:
        return None
    try:
        amount = Decimal(m.group(2).replace(",", "."))
    except InvalidOperation:
        return None
    unit = m.group(3).lower()
    if unit in ("kg", "l"):
        amount *= 1000
        unit = "g" if unit == "kg" else "ml"
    if amount <= 0 or amount != amount.to_integral_value():
        return None
    count = int(m.group(1)) if m.group(1) else None
    if count is not None and count < 1:
        return None
    return (count, int(amount), unit)


def _article(raw):
    if not isinstance(raw, dict):
        raise InputError("article must be an object")
    if not raw.get("id") or not raw.get("versionId") or not raw.get("label"):
        raise InputError("article requires id, versionId, label")
    a = deepcopy(raw)
    a.setdefault("organic", None)
    a.setdefault("brandKind", infer_brand_kind(a.get("brandName"), a.get("retailerId")))
    if a["organic"] is not None and type(a["organic"]) is not bool:
        raise InputError("organic must be true, false or null")
    if a["brandKind"] not in BRAND_KINDS:
        raise InputError("invalid brandKind")
    if a.get("gtin") is not None:
        a["gtin"] = normalize_gtin(a["gtin"])
    q = a.get("quantity")
    if q is not None:
        if not isinstance(q, dict) or q.get("unit") not in ("g", "ml", "piece", "portion") or q.get("basis") not in (
                "NET", "DRAINED", "GROSS", "PIECE", "PER_PORTION", "UNKNOWN") or type(q.get("confirmed")) is not bool:
            raise InputError("invalid quantity")
        if q.get("amount") is not None:
            _int(q["amount"], "quantity.amount", 0)
        if q.get("packageCount") is not None:
            _int(q["packageCount"], "quantity.packageCount", 1)
    return a


def normalize_article(raw, source=None):
    """Validate a catalog SKU without treating source records as user-confirmed."""
    article = _article(raw)
    if source is not None:
        if not isinstance(source, dict) or not source.get("origin") or source.get("rightsStatus") not in (
                "PERMITTED", "UNVERIFIED", "RESTRICTED"):
            raise InputError("invalid source provenance")
        article["importSource"] = deepcopy(source)
    return article



def import_off_snapshot(snapshot, product_id, version_id, retailer_id=None, source=None):
    """Map an already obtained OFF record, not a live request.

    All source facts are unconfirmed and caller-owned; no product identity,
    organic=false, FoodType or gross/net basis is silently invented.
    """
    if not isinstance(snapshot, dict):
        raise InputError("OFF snapshot must be an object")
    product = snapshot.get("product", snapshot)
    if not isinstance(product, dict) or not isinstance(product_id, str) or not product_id.strip() \
            or not isinstance(version_id, str) or not version_id.strip():
        raise InputError("OFF product and caller-provided stable IDs required")
    label = product.get("product_name_de") or product.get("product_name")
    if not isinstance(label, str) or not label.strip():
        raise InputError("OFF product name missing; manual identification required")
    gtin = product.get("code") or snapshot.get("code")
    if product.get("code") and snapshot.get("code"):
        if gtin_lookup_key(product["code"]) != gtin_lookup_key(snapshot["code"]):
            raise InputError("OFF product and response barcode disagree")
    if gtin is not None:
        gtin = normalize_gtin(gtin)
    brands = product.get("brands")
    brand = brands.strip() if isinstance(brands, str) and brands.strip() and "," not in brands else None
    tags = product.get("labels_tags")
    tags = tags if isinstance(tags, list) else []
    known_organic = any(tag in ("en:organic", "de:bio", "de:aus-kontrolliert-biologischem-anbau")
                        for tag in tags)
    package = _pack(product.get("quantity"))
    qty = None
    if package is not None:
        count, amount, unit = package
        qty = {"amount": amount, "unit": unit, "basis": "UNKNOWN", "confirmed": False}
        if count is not None:
            qty["packageCount"] = count
    article = {
        "id": product_id, "versionId": version_id, "retailerId": retailer_id,
        "label": label.strip(), "gtin": gtin, "retailerArticleId": None,
        "foodTypeId": None, "brandName": brand,
        "brandKind": infer_brand_kind(brand, retailer_id),
        "organic": True if known_organic else None,
        "quantity": qty, "attributes": {}
    }
    if not isinstance(source, dict):
        raise InputError("OFF snapshot requires explicit acquisition provenance")
    if source.get("dataQuality") not in ("SOURCED", "UNKNOWN"):
        raise InputError("unconfirmed OFF data cannot be marked CONFIRMED")
    _timestamp(source.get("observedAt"), "source.observedAt")
    return normalize_article(article, source)


def _contract_article(a):
    return {
        "label": a["label"], "foodTypeId": a.get("foodTypeId"),
        "gtin": a.get("gtin"), "retailerArticleId": a.get("retailerArticleId"),
        "brandName": a.get("brandName"), "brandKind": a["brandKind"],
        "organic": a["organic"], "attributes": deepcopy(a.get("attributes", {})),
        "quantity": deepcopy(a.get("quantity"))
    }


def classify_receipt_line(line):
    """Preserve exact raw OCR text. Proposed classifications never confirm facts."""
    if not isinstance(line, dict) or not isinstance(line.get("rawText"), str):
        raise InputError("rawText required")
    raw = line["rawText"]
    head = _text(raw)
    warnings = []
    provided = line.get("lineKind", "UNKNOWN")
    if provided not in LINE_KINDS:
        raise InputError("invalid lineKind")
    kind = provided
    if kind == "UNKNOWN":
        if re.search(r"\b(retoure|rückgabe|rueckgabe|storno|gutschrift)\b", head):
            kind = "RETURN"
        elif re.search(r"\b(pfand|leergut)\b", head):
            kind = "DEPOSIT"
        elif re.search(r"\b(rabatt|coupon|gutschein|nachlass)\b", head):
            kind = "DISCOUNT"
        elif re.search(r"\b(tasche|waschmittel|spülmittel|spuelmittel)\b", head):
            kind = "NON_FOOD"
        elif re.search(r"\b(rückgeld|rueckgeld|gegeben|barzahlung|kartenzahlung|zwischensumme|summe|gesamt|mwst|ust)\b", head):
            kind = "UNKNOWN"
            warnings.append("payment_or_total_row")
        else:
            kind = "UNKNOWN"  # Text alone is not evidence of FOOD.
    amount = line.get("amountCents")
    if amount is not None:
        _int(amount, "amountCents")  # Negative is allowed for RETURN/DISCOUNT only.
    else:
        found = _PRICE.search(raw)
        if found:
            amount = int(found.group(1).replace(",", "").replace(".", ""))
        elif re.search(r"\b\d{2,}[A-Z]\s*$", raw):
            warnings.append("malformed_ocr_price")
    if amount is not None and amount < 0 and kind not in ("RETURN", "DISCOUNT"):
        warnings.append("negative_non_return_amount")
        kind = "UNKNOWN"
    if line.get("confirmed", False) is not True:
        warnings.append("unconfirmed_ocr")
    return {
        "lineId": line.get("lineId", ""), "receiptId": line.get("receiptId", ""),
        "retailerId": line.get("retailerId", ""), "storeId": line.get("storeId"),
        "rawText": raw, "lineKind": kind, "amountCents": amount,
        "quantity": deepcopy(line.get("quantity")), "confirmed": line.get("confirmed") is True,
        "purchaseAt": line.get("purchaseAt"), "gtin": line.get("gtin"),
        "retailerArticleId": line.get("retailerArticleId"),
        "linkedArticle": None, "source": deepcopy(line.get("source")),
        "egProductdaten": {"warnings": warnings}
    }


def _alias_heads(ledger):
    """Validate a persisted decision history before deriving active heads.

    A reference across merchant/text boundaries or a duplicated decision ID must
    not suppress a valid alias or turn a stale choice into a confirmed match.
    """
    groups = defaultdict(list)
    ids = {}
    for event in ledger:
        if not isinstance(event, dict) or event.get("confirmed") is not True or not event.get("reason") \
                or not event.get("decisionId") or not event.get("retailerId") or not event.get("rawText") \
                or event.get("action") not in ("CONFIRM", "CORRECT", "REVOKE"):
            raise InputError("invalid or unconfirmed alias event")
        _timestamp(event.get("decidedAt"), "alias.decidedAt")
        if event["action"] != "REVOKE" and (not event.get("productId") or not event.get("versionId")):
            raise InputError("alias event requires a concrete product version")
        key = (_key(event["retailerId"]), _text(event["rawText"]))
        if event["decisionId"] in ids:
            raise ConflictError("duplicate alias decisionId in history")
        ids[event["decisionId"]] = key
        groups[key].append(event)
    for events in groups.values():
        for event in events:
            parent = event.get("expectedPreviousId")
            if parent is not None:
                if parent == event["decisionId"] or (parent in ids and ids[parent] != ids[event["decisionId"]]):
                    raise ConflictError("alias decision references itself or a different merchant/text")
    result = {}
    for key, events in groups.items():
        superseded = {e.get("expectedPreviousId") for e in events if e.get("expectedPreviousId")}
        result[key] = [e for e in events if e.get("decisionId") not in superseded]
    return result


def resolve_alias_decision(ledger, decision):
    """Immutable decision ledger with compare-and-swap and idempotent replay."""
    if not isinstance(ledger, list) or not isinstance(decision, dict):
        raise InputError("invalid alias inputs")
    if decision.get("confirmed") is not True or not decision.get("reason") or not decision.get("decisionId"):
        raise InputError("explicit confirmed alias decision and reason required")
    if not decision.get("retailerId") or not decision.get("rawText"):
        raise InputError("retailer-bound alias requires merchant and text")
    _timestamp(decision.get("decidedAt"), "decidedAt")
    action = decision.get("action")
    if action not in ("CONFIRM", "CORRECT", "REVOKE"):
        raise InputError("invalid alias action")
    if action != "REVOKE" and (not decision.get("productId") or not decision.get("versionId")):
        raise InputError("alias needs concrete product and version")
    for old in ledger:
        if old["decisionId"] == decision["decisionId"]:
            if old == decision:
                return deepcopy(ledger)
            raise ConflictError("decisionId replay changed content")
    key = (_key(decision["retailerId"]), _text(decision["rawText"]))
    head = _alias_heads(ledger).get(key, [])
    if len(head) > 1:
        raise ConflictError("ambiguous alias heads; manual resolution required")
    previous_id = head[0]["decisionId"] if head else None
    if decision.get("expectedPreviousId") != previous_id:
        raise ConflictError("stale alias decision")
    if action == "CONFIRM" and previous_id is not None:
        raise ConflictError("use CORRECT to supersede existing alias")
    if action in ("CORRECT", "REVOKE") and previous_id is None:
        raise ConflictError("cannot revise nonexisting alias")
    return deepcopy(ledger) + [deepcopy(decision)]


def find_candidates(query, catalog, aliases=()):
    """Rank candidates; never convert an OCR suggestion into a purchase.
    
    Returns a list of contract ProductMatch payloads with namespaced local identity.
    """
    if not isinstance(query, dict) or not query.get("retailerId") or not isinstance(catalog, list):
        raise InputError("retailerId and catalog required")
    merchant = _key(query["retailerId"])
    supplied_gtin = query.get("gtin")
    if supplied_gtin is not None:
        supplied_gtin = normalize_gtin(supplied_gtin)
    supplied_sku = _key(query.get("retailerArticleId"))
    raw = query.get("rawText", "")
    original = _text(re.sub(_PRICE, "", raw))
    words = set(_TOKENS.findall(original))
    hint = _pack(raw)
    bio_hint = bool(re.search(r"(?<!\w)bio(?!\w)|\bökologisch\b", original))
    heads = _alias_heads(aliases).get((merchant, _text(raw)), [])
    matching_alias_pairs = {(h.get("productId"), h.get("versionId"))
                            for h in heads if h.get("action") != "REVOKE"}
    ambiguous_alias = len(matching_alias_pairs) > 1 or len(heads) > 1
    catalog_rows = [_article(row) for row in catalog]
    # Alias points to a concrete version. Only the current supplied version of
    # a product can be reused automatically; older versions remain historical.
    current_versions = {}
    for row in catalog_rows:
        current_versions.setdefault(row["id"], set()).add(row["versionId"])
    results = []
    for a in catalog_rows:
        evidence, conflicts, score = [], [], 0
        a_gtin = a.get("gtin")
        if supplied_gtin:
            if a_gtin is not None and gtin_lookup_key(a_gtin) == gtin_lookup_key(supplied_gtin):
                evidence.append("valid_gtin_exact")
                score += 100
            elif a_gtin:
                conflicts.append("different_gtin")
        if supplied_sku and _key(a.get("retailerArticleId")) == supplied_sku:
            if _key(a.get("retailerId")) == merchant:
                evidence.append("retailer_sku_exact")
                score += 90
            else:
                conflicts.append("retailer_sku_wrong_merchant")
        elif supplied_sku and a.get("retailerArticleId") and _key(a.get("retailerId")) == merchant:
            conflicts.append("different_retailer_sku")
        if (a["id"], a["versionId"]) in matching_alias_pairs:
            if _key(a.get("retailerId")) in ("", merchant):
                evidence.append("user_confirmed_retailer_alias_version")
                score += 70
            else:
                conflicts.append("alias_merchant_conflict")
        if _key(a.get("retailerId")) not in ("", merchant) and a.get("brandKind") == "PRIVATE_LABEL":
            conflicts.append("private_label_wrong_merchant")
        name = _text(a["label"])
        if original and original == name:
            evidence.append("name_exact_unverified")
            score += 30
        elif words:
            overlap = len(words & set(_TOKENS.findall(name)))
            if overlap:
                evidence.append(f"name_token_overlap:{overlap}")
                score += min(20, overlap * 7)
        aq = a.get("quantity")
        if hint and aq and aq.get("confirmed") is True and aq.get("amount") is not None:
            c, amount, unit = hint
            if aq["unit"] != unit or aq["amount"] != amount or (
                    c is not None and aq.get("packageCount") is not None and c != aq["packageCount"]):
                conflicts.append("package_or_unit_conflict")
            else:
                evidence.append("confirmed_package_agrees")
                score += 15
        if bio_hint and a["organic"] is False:
            conflicts.append("explicit_bio_conflict")
        elif bio_hint and a["organic"] is True:
            evidence.append("bio_claim_agrees")
            score += 5
        if query.get("foodTypeId") and query["foodTypeId"] == a.get("foodTypeId"):
            evidence.append("food_type_agrees_not_identity")
            score += 5
        if not evidence:
            continue
        strong = "valid_gtin_exact" in evidence or "retailer_sku_exact" in evidence
        alias_confirmed = "user_confirmed_retailer_alias_version" in evidence
        if alias_confirmed and a.get("currentVersionConfirmed") is not True:
            conflicts.append("current_product_version_not_confirmed")
        if alias_confirmed and len(current_versions.get(a["id"], set())) > 1:
            if a.get("currentVersionConfirmed") is not True:
                conflicts.append("stale_or_unresolved_product_version")
        uncertain_alias = "current_product_version_not_confirmed" in conflicts
        review_conflicts = {"current_product_version_not_confirmed",
                            "stale_or_unresolved_product_version"}
        severe = any(c not in review_conflicts for c in conflicts)
        if strong and not severe:
            level = "EXACT_SKU"
        elif evidence and not severe:
            level = "SAME_FOOD_VARIANT" if score >= 20 else "UNKNOWN"
        else:
            level = "UNKNOWN"
        status = ("REJECTED" if severe else
                  "AMBIGUOUS" if ambiguous_alias or uncertain_alias else
                  "CONFIRMED_BY_USER" if alias_confirmed else
                  "SUGGESTED")
        result = {
            "requestId": str(query.get("requestId") or "unidentified-request"),
            "candidate": _contract_article(a), "matchLevel": level, "status": status,
            "confidence": None, "evidence": evidence,
            "conflicts": conflicts,
            "egProductdaten": {
                "productId": a["id"], "versionId": a["versionId"], "rankScore": score,
                "requiresPurchaseConfirmation": True
            }
        }
        results.append(result)
    results.sort(key=lambda x: (-x["egProductdaten"]["rankScore"],
                                x["egProductdaten"]["productId"], x["egProductdaten"]["versionId"]))
    viable = [x for x in results if x["status"] != "REJECTED"]
    # More than one viable answer, or repeated GTIN with incompatible versions: no unique winner.
    if len(viable) > 1:
        high = viable[0]["egProductdaten"]["rankScore"]
        for x in viable:
            if x["egProductdaten"]["rankScore"] >= high - 15:
                x["status"] = "AMBIGUOUS"
                x["conflicts"].append("multiple_plausible_products")
    return results


def to_historical_price_observation(receipt, line, article):
    """Gate paid historical observations on *separate* explicit confirmations.

    Returns {'observation': contract payload | None, 'reason': symbolic reason | None}.
    Never mutates input, any database, or any state.
    """
    def fail(reason):
        return {"observation": None, "reason": reason}
    if not isinstance(receipt, dict) or not isinstance(line, dict):
        raise InputError("receipt and line objects required")
    if receipt.get("purchaseConfirmed") is not True or line.get("confirmed") is not True:
        return fail("UNCONFIRMED_PURCHASE_OR_LINE")
    if line.get("productConfirmed") is not True:
        return fail("UNCONFIRMED_PRODUCT_LINK")
    if line.get("lineKind") != "FOOD":
        return fail("NON_FOOD_DISCOUNT_DEPOSIT_OR_RETURN")
    for k in ("purchaseId", "receiptId", "retailerId", "confirmedAt"):
        if not receipt.get(k):
            return fail("MISSING_" + k.upper())
    if not receipt.get("purchaseAt") and not receipt.get("purchasedOn"):
        return fail("MISSING_PURCHASE_DATE")
    if not line.get("lineId") or line.get("receiptId") != receipt["receiptId"]:
        return fail("INVALID_LINE_IDENTITY")
    if line.get("retailerId") != receipt["retailerId"]:
        return fail("MERCHANT_MISMATCH")
    try:
        purchased = _timestamp(receipt["purchaseAt"], "purchaseAt") if receipt.get("purchaseAt") else None
        confirmed_at = _timestamp(receipt["confirmedAt"], "confirmedAt")
        purchase_on = receipt.get("purchasedOn")
        if purchase_on is not None:
            if not isinstance(purchase_on, str) or date.fromisoformat(purchase_on).isoformat() != purchase_on:
                raise ValueError("invalid ISO date")
        elif purchased is not None:
            purchase_on = purchased.date().isoformat()
        if purchased is not None and purchased.date().isoformat() != purchase_on:
            return fail("PURCHASE_DATE_CONFLICT")
        if purchased is not None and confirmed_at < purchased:
            return fail("CONFIRMATION_PRECEDES_PURCHASE")
        if purchased is None and confirmed_at.date().isoformat() < purchase_on:
            return fail("CONFIRMATION_PRECEDES_PURCHASE")
        a = _article(article)
    except (InputError, ValueError):
        return fail("INVALID_DATE_OR_ARTICLE")
    if line.get("productId") != a["id"] or line.get("versionId") != a["versionId"]:
        return fail("PRODUCT_VERSION_MISMATCH")
    if line.get("gtin") is not None:
        try:
            if a.get("gtin") is None or gtin_lookup_key(line["gtin"]) != gtin_lookup_key(a["gtin"]):
                return fail("BARCODE_CONFLICT")
        except InputError:
            return fail("INVALID_BARCODE")
    amount = line.get("amountCents")
    units = line.get("purchaseUnits")
    if type(amount) is not int or amount < 0:
        return fail("UNKNOWN_OR_INVALID_PRICE")
    if type(units) is not int or units < 1 or line.get("unitsConfirmed") is not True:
        return fail("UNKNOWN_PURCHASE_UNITS")
    if line.get("discountReconciled") is not True:
        return fail("DISCOUNT_ACCOUNTING_UNKNOWN")
    if line.get("unallocatedDiscount") is True:
        return fail("UNALLOCATED_DISCOUNT")
    discount = line.get("allocatedDiscountCents", 0)
    if type(discount) is not int or discount < 0 or discount > amount:
        return fail("INVALID_DISCOUNT")
    if line.get("discountApplied") is True and "allocatedDiscountCents" not in line:
        return fail("UNALLOCATED_DISCOUNT")
    if line.get("amountExcludesDeposit") is not True:
        return fail("DEPOSIT_ACCOUNTING_UNKNOWN")
    paid = amount - discount
    if paid % units:
        return fail("NONINTEGRAL_UNIT_PRICE")
    if line.get("storeId") and receipt.get("storeId") and line["storeId"] != receipt["storeId"]:
        return fail("STORE_MISMATCH")
    store = receipt.get("storeId")
    if store is not None and not isinstance(store, str):
        return fail("INVALID_STORE")
    scope = {"retailerId": receipt["retailerId"], "storeId": store or None,
             "scopeType": "STORE_CONFIRMED" if store else "UNKNOWN"}
    key = "\x1f".join((str(receipt["purchaseId"]), str(receipt["receiptId"]), str(line["lineId"])))
    observation_id = "receipt-" + sha256(key.encode("utf-8")).hexdigest()[:32]
    result = {
        "observationId": observation_id, "article": _contract_article(a), "scope": scope,
        "priceCents": paid // units, "currency": "EUR",
        "priceKind": "HISTORICAL_PAID", "validFrom": None, "validUntil": None,
        "depositCents": line.get("depositPerUnitCents"),
        "conditional": [], "availability": "UNKNOWN",
        "source": {"origin": "local_user_confirmed_receipt", "url": None,
                   "observedAt": receipt["confirmedAt"], "evidenceKind": "USER_CONFIRMED_RECEIPT",
                   "rightsStatus": "UNVERIFIED", "dataQuality": "CONFIRMED", "parserVersion": None},
        "egProductdaten": {"purchaseAt": receipt.get("purchaseAt"), "purchasedOn": purchase_on,
                          "purchaseId": receipt["purchaseId"],
                          "receiptId": receipt["receiptId"], "lineId": line["lineId"],
                          "productId": a["id"], "versionId": a["versionId"],
                          "purchaseUnits": units, "linePaidCents": paid,
                          "allocatedDiscountCents": discount,
                          "notCurrentRetailPrice": True}
    }
    if result["depositCents"] is not None:
        if type(result["depositCents"]) is not int or result["depositCents"] < 0:
            return fail("INVALID_DEPOSIT")
    return {"observation": result, "reason": None}


def build_price_memory(purchases):
    """Idempotent pure fold of confirmed purchase/line/article tuples."""
    observations = {}
    unresolved = []
    for record in purchases:
        result = to_historical_price_observation(record["receipt"], record["line"], record["article"])
        obs = result["observation"]
        if obs is None:
            unresolved.append({"receiptId": record["receipt"].get("receiptId"),
                               "lineId": record["line"].get("lineId"), "reason": result["reason"]})
            continue
        oid = obs["observationId"]
        if oid in observations and observations[oid] != obs:
            raise ConflictError("same purchase line with conflicting confirmation or price")
        observations[oid] = obs
    return {"observations": [observations[k] for k in sorted(observations)],
            "unresolved": unresolved}


def apply_memory_correction(snapshot, event):
    """Pure revisioned correction/retraction; app persists only after confirmation.

    snapshot: {'entries': {observationId: {'revision': int, 'observation': object|null}},
               'events': {eventId: event}}.
    """
    if event.get("confirmed") is not True or not event.get("eventId") or not event.get("observationId"):
        raise InputError("confirmed correction event with id required")
    if event.get("action") not in ("RETRACT", "REPLACE"):
        raise InputError("unknown correction action")
    _timestamp(event.get("decidedAt"), "decidedAt")
    out = deepcopy(snapshot)
    events = out.setdefault("events", {})
    entries = out.setdefault("entries", {})
    event_id = event["eventId"]
    if event_id in events:
        if events[event_id] == event:
            return out
        raise ConflictError("correction event replay changed")
    oid = event["observationId"]
    previous = entries.get(oid)
    if previous is None or type(event.get("expectedRevision")) is not int or previous["revision"] != event["expectedRevision"]:
        raise ConflictError("missing or stale observation revision")
    if event["action"] == "REPLACE":
        if not all(isinstance(event.get(k), dict) for k in ("receipt", "line", "article")):
            raise InputError("correction must contain confirmed purchase, line and article evidence")
        rebuilt = to_historical_price_observation(event["receipt"], event["line"], event["article"])
        replacement = rebuilt["observation"]
        if replacement is None:
            raise InputError("unconfirmed replacement: " + rebuilt["reason"])
        if replacement["observationId"] != oid:
            raise ConflictError("correction references another purchase line")
        if event.get("replacement") is not None and event["replacement"] != replacement:
            raise ConflictError("replacement differs from rebuilt confirmed purchase")
        new_value = replacement
    else:
        new_value = None
    entries[oid] = {"revision": previous["revision"] + 1, "observation": new_value}
    events[event_id] = deepcopy(event)
    return out


def as_contract(message_type, payload, created_at, trace_id, producer="EG-Produktdaten"):
    """Envelope for Architecture v1. Explicit clock injected by caller."""
    if message_type not in ("product.match", "receipt.line", "price.observation"):
        raise InputError("unsupported messageType")
    _timestamp(created_at, "createdAt")
    if not trace_id or not isinstance(payload, dict):
        raise InputError("traceId and payload required")
    return {"contractVersion": CONTRACT_VERSION, "messageType": message_type,
            "meta": {"producer": producer, "createdAt": created_at, "traceId": trace_id},
            "payload": deepcopy(payload)}
