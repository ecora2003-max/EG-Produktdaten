"""Deterministic offline identity and historical-receipt price engine."""
from .core import (InputError, ConflictError, normalize_gtin, gtin_lookup_key,
                   infer_brand_kind, normalize_article, import_off_snapshot, classify_receipt_line,
                   resolve_alias_decision, find_candidates,
                   to_historical_price_observation, build_price_memory,
                   apply_memory_correction, as_contract)
