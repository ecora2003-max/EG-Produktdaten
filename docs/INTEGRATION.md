# Integrations-Ports – Produktdaten
Beispiel-Fachschnittstellen (Sprache/Framework intern frei):
- `findCandidates(receiptLine, catalogSnapshot, aliasSnapshot) -> CandidateMatch[]`
- `resolveAliasDecision(previousSnapshot, confirmedDecision) -> ProposedAliasState`
- `classifyReceiptLine(rawLine, merchantContext) -> ReceiptLineProposal`
- `toHistoricalPriceObservation(confirmedReceiptLine, linkedArticle, purchaseContext) -> PriceObservation | UnresolvedReason`

Ein Eingang ist **immer ein expliziter Snapshot**; keine direkten App-/Room-Zugriffe. Vorschläge ≠ bestätigte Entscheidungen. Validierter Vertrag: `EG-Architecture/contracts/v1`. Codex bindet die reinen Ports an vorhandene `RecognitionReader/Operations`, `ReceiptParser`, `alias_decisions`, `receipt_scan_resolutions`, `FoodStore` an; Buchung bleibt in der Haupt-App atomar/idempotent.

Die Modulfunktionen müssen neben dem Happy Path folgende Fälle zeigen: kein Produktkandidat, mehrere, stale Aliasversion, Händlerwechsel, zurückgenommener Alias, identischer Bon zweimal, unklare Stückmenge, kombinierter Rabatt und fehlende Gesamtsumme. Synthetische Fixtures plus reproduzierbare Tests mit jedem Release.
