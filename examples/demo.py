"""Run via: python examples/demo.py; synthetic data only."""
import json
from eg_productdaten.core import find_candidates, to_historical_price_observation, as_contract

ARTICLE = {
    "id": "synthetic-oats", "versionId": "s-v1", "retailerId": "EDEKA",
    "label": "GUT & GÜNSTIG Haferflocken 500 g",
    "gtin": "4006381333931", "retailerArticleId": "EX-001",
    "brandName": "GUT & GÜNSTIG", "organic": False,
    "quantity": {"amount": 500, "unit": "g", "basis": "NET", "confirmed": True}
}
STAMP = "2026-10-31T15:00:00+01:00"
matches = find_candidates({"requestId": "sample", "retailerId": "EDEKA",
                           "gtin": ARTICLE["gtin"]}, [ARTICLE])
print(json.dumps(as_contract("product.match", matches[0], STAMP, "sample"), indent=2, ensure_ascii=False))
receipt = {"purchaseId": "P-EXAMPLE", "receiptId": "R-EXAMPLE", "retailerId": "EDEKA",
           "storeId": None, "purchaseAt": STAMP, "confirmedAt": STAMP, "purchaseConfirmed": True}
line = {"receiptId": "R-EXAMPLE", "lineId": "L1", "retailerId": "EDEKA",
        "productId": "synthetic-oats", "versionId": "s-v1",
        "lineKind": "FOOD", "amountCents": 199, "purchaseUnits": 1,
        "confirmed": True, "productConfirmed": True, "unitsConfirmed": True,
        "discountReconciled": True, "amountExcludesDeposit": True}
result = to_historical_price_observation(receipt, line, ARTICLE)
print(json.dumps(as_contract("price.observation", result["observation"], STAMP, "example"),
                 indent=2, ensure_ascii=False))
