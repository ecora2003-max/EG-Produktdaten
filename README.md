# EG-Produktdaten — Produktidentifikation und Preisgedächtnis

Offline-Referenzengine für erklärbare Produktkandidaten, händlergebundene Bon-Aliase und historische Preisbeobachtungen ausschließlich aus **bestätigten Käufen**. Keine OCR, Kamera, Cloud, zweite Produktivdatenbank, Bestands- oder Zahlungsbuchung.

Vertrag: [EG-Architecture](https://github.com/ecora2003-max/EG-Architecture), 1.0.0-draft, Commit d22862739bd0e3ef8451ce029e54f7c33ee53e40; Testkopie unter contracts/v1/.

## Tests (Python 3.11+)

    python -m pip install -r requirements-dev.txt
    python -m unittest discover -s tests -p 'test_*.py' -v
    python -m compileall -q eg_productdaten tests
    python -m examples.demo

Die Engine benötigt zur Laufzeit nur die Python-Standardbibliothek. jsonschema ist ausschließlich eine Testabhängigkeit. GitHub Actions prüft bei Push und PR automatisiert.

## Fachports

- normalize_gtin, gtin_lookup_key: Prüfziffer, führende Nullen, 14-stelliger Android-Lookup-Key.
- normalize_article, infer_brand_kind: unveränderliche Produktversion, Händlerkontext, Menge, Bio-Dreistatus, konservative Eigenmarken.
- find_candidates: erklärbare Liste von Produktmatches mit Konflikten; keine implizite Kaufbestätigung.
- resolve_alias_decision: ausdrücklich bestätigter, revisionssicherer Aliasverlauf, Händler- und Versionsbindung, Korrektur und Rücknahme.
- classify_receipt_line: Rohtext, Betrag und vorsichtige Kategorien; unbestätigte OCR bleibt unbestätigt.
- to_historical_price_observation: Historischer bezahlter Packpreis nur aus vollständig bestätigtem Kauf und eindeutig zugeordneten Rabatt-/Pfand-/Mengenwerten; sonst Grundcode.
- build_price_memory: Idempotenz nach tatsächlicher Kauf- und Positions-ID; Konflikt statt Überschreiben.
- apply_memory_correction: bestätigte Korrektur oder Rücknahme mit erwarteter Revision.
- as_contract: versionierter Architektur-Umschlag.

Ein-/Ausgaben: [examples/demo.py](examples/demo.py), [docs/INTEGRATION.md](docs/INTEGRATION.md). Prüfkriterien: [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md). Status: [docs/STATUS.md](docs/STATUS.md).

**Wichtig:** Historische Bonpreise sind keine heutigen Marktpreise. Die Kotlin-Portierung für die bestehende Room-App ist ausdrücklich Teil der späteren Codex-Integration; diese Python-Referenz ist keine direkt ausführbare Android-Bibliothek. Keine unbestätigten Produktpreise, keine persönlichen Bons, keine Live-Quellenrechte.


## Neuer Architekturstand: 1.1.0-draft (expliziter Adapter)

Chat 1 hat [ADR-014/016/017](docs/V11_IMPACT.md) und einen separaten **nicht freigegebenen** `1.1.0-draft`-Vertrag veröffentlicht. Der ursprüngliche `1.0.0-draft`-Pfad bleibt unverändert. Der bewusste Opt-in-Adapter `eg_productdaten.v11` produziert nur die bisherigen drei Produktdaten-Nachrichtentypen mit `meta.usageContext`. Schema: `contracts/v1.1/contract.schema.json`, vom Architektur-Blob `dca777d219307a90bf3d4dff6189fbf12476c508` unverändert übernommen.

- `match_v11(...)`: Produktvorschläge und Konflikte, privat oder Forschungsmodus; keine Bestell- oder Kaufwirkung.
- `receipt_proposal_v11(...)`: ungeprüfte Bonpositionen ausschließlich privat, nie bezahlt.
- `historical_purchase_v11(...)`: ein privater historischer Preis **nur nach erneuter Prüfung** eines bestätigten, nicht stornierten Kaufs samt Produktversion, Rabatt, Pfand und Menge.
- `historical_snapshot_v11(..., evidence_cutoff_at=...)`: as-of-gefilterte, idempotente bestätigte Bonhistorie; keine später bestätigten Preise als damaliges Wissen.
- Alle `APP_DISPLAY`-Ausgaben aus diesen Ports sind gesperrt, unabhängig von vermeintlichen Produkt- oder Händlerrechten; externe Live-Preisanzeige ist hier ausdrücklich nicht implementiert.

Die aktualisierten Tests prüfen beide Vertragsfassungen einschließlich Rechte- und Negativfällen. Der neue v1.1-Adapter ist **DRAFT_ADAPTER_TESTED**, nicht `STABLE` oder `INTEGRATED`. Android/Codex muss den Host-/Room-/UI-Rechtefilter und App-Regression weiterhin selbst nachweisen.
