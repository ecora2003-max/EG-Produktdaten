"""Explicit, opt-in EG-Architecture v1.1.0-draft read-only adapters.

Not a replacement for v1.0. No public/live price feed, purchases, or Room writes.
Unconfirmed receipt OCR remains a proposal, never historical purchase evidence.
"""
from copy import deepcopy
from datetime import datetime

from .core import (InputError, as_contract, classify_receipt_line,
                   find_candidates, to_historical_price_observation)

DRAFT_VERSION = "1.1.0-draft"
PRIVATE = "PRIVATE_USER_HISTORY"
RESEARCH = "RESEARCH_ONLY"


def _at(value, name):
    if not isinstance(value, str):
        raise InputError(name + ": timezone-aware timestamp required")
    try:
        d = datetime.fromisoformat(value)
        if d.utcoffset() is None:
            raise ValueError("missing zone")
        return d
    except ValueError as exc:
        raise InputError(name + ": timezone-aware timestamp required") from exc


def _envelope(message_type, payload, created_at, trace_id, usage_context):
    """Only opt-in supported message types; never repurpose v1 envelope."""
    if usage_context not in (PRIVATE, RESEARCH):
        raise InputError("APP_DISPLAY denied: this module cannot license external price display")
    _at(created_at, "createdAt")
    if not isinstance(trace_id, str) or not trace_id.strip():
        raise InputError("traceId required")
    if message_type not in ("product.match", "receipt.line", "price.observation"):
        raise InputError("Unsupported v1.1 producer message")
    return {
        "contractVersion": DRAFT_VERSION,
        "messageType": message_type,
        "meta": {"producer": "EG-Produktdaten", "createdAt": created_at,
                 "traceId": trace_id, "usageContext": usage_context},
        "payload": deepcopy(payload)
    }


def match_v11(query, catalog, aliases, *, created_at, trace_id, usage_context=PRIVATE):
    """Match suggestions, explicitly marked private/research; not purchases."""
    # Validate the security context even if the candidate list is empty.
    _envelope("product.match", {}, created_at, trace_id, usage_context)
    return [_envelope("product.match", payload, created_at, trace_id, usage_context)
            for payload in find_candidates(query, catalog, aliases)]


def receipt_proposal_v11(line, *, created_at, trace_id, usage_context=PRIVATE):
    """Preserve receipt text and UNKNOWN status; never user-confirm automatically."""
    if usage_context != PRIVATE:
        raise InputError("Receipt OCR may only be transferred in private user history")
    proposal = classify_receipt_line(line)
    return _envelope("receipt.line", proposal, created_at, trace_id, usage_context)


def historical_purchase_v11(receipt, line, article, *, created_at, trace_id,
                            usage_context=PRIVATE):
    """Rebuild from confirmed purchase, never relabel arbitrary external prices.

    Returns {"message": valid-draft-envelope|null, "reason": code|null}.
    Every successful observation is HISTORICAL_PAID; it is NOT an APP_DISPLAY
    alternative or a current store price.
    """
    if usage_context != PRIVATE:
        raise InputError("Historical paid receipts only in PRIVATE_USER_HISTORY")
    _at(created_at, "createdAt")
    result = to_historical_price_observation(receipt, line, article)
    if result["observation"] is None:
        return {"message": None, "reason": result["reason"]}
    payload = result["observation"]
    if payload["priceKind"] != "HISTORICAL_PAID" or (
            payload["source"]["evidenceKind"] != "USER_CONFIRMED_RECEIPT") or (
            payload["source"]["dataQuality"] != "CONFIRMED"):
        raise InputError("Private historical price provenance mismatch")
    return {"message": _envelope("price.observation", payload, created_at,
                                 trace_id, usage_context), "reason": None}


def historical_snapshot_v11(records, *, created_at, trace_id, evidence_cutoff_at):
    """Private, as-of filtered price-memory snapshots for downstream comparison.

    A record is {receipt,line,article}; every input is reverified.
    Observations learned *after* cutoff are invisible to an earlier comparison.
    Different real purchases survive; scans/retries with same purchase line dedupe.
    Conflicting confirmations for the same purchase line are rejected.
    No claim that these prices are valid/current at cutoff.
    """
    from .core import ConflictError
    cutoff = _at(evidence_cutoff_at, "evidenceCutoffAt")
    _at(created_at, "createdAt")
    if not isinstance(records, list):
        raise InputError("records list required")
    observations = {}
    unresolved = []
    for row in records:
        if not isinstance(row, dict) or not all(k in row for k in ("receipt", "line", "article")):
            raise InputError("each record needs receipt, line, article")
        built = historical_purchase_v11(
            row["receipt"], row["line"], row["article"],
            created_at=created_at, trace_id=trace_id)
        if built["message"] is None:
            unresolved.append({"receiptId": row["receipt"].get("receiptId"),
                               "lineId": row["line"].get("lineId"),
                               "reason": built["reason"]})
            continue
        msg = built["message"]
        obs = msg["payload"]
        if _at(obs["source"]["observedAt"], "observedAt") > cutoff:
            continue
        oid = obs["observationId"]
        if oid in observations and observations[oid] != msg:
            raise ConflictError("conflicting confirmed historical price for same purchase line")
        observations[oid] = msg
    return {"messages": [deepcopy(observations[k]) for k in sorted(observations)],
            "unresolved": unresolved, "evidenceCutoffAt": evidence_cutoff_at,
            "completeness": "PARTIAL" if unresolved else "UNKNOWN"}
