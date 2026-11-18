# EG-Produktdaten – Fachkern-/Fixture-Referenz

**Stand 18.11.2026:** Historischer offline verifizierter Referenzkern für Produktidentität, GTIN/SKU, Bonalias und datierte Preisbeobachtungen. Die aktuelle Kotlin-/Room-/UI-Integration läuft ausschließlich in [Ernaerungsgedaechnis](https://github.com/ecora2003-max/Ernaerungsgedaechnis).

- **Kein separater dauerhafter Entwicklungsauftrag** für „Chat 3“, kein Nacharbeiten historischer Meilensteine, keine eigene Freigabe-/ADR-Abstimmungsrunde. Nur bei gezieltem Auftrag neue Referenzfälle/Tests liefern.
- Historische `docs/STATUS.md`, `docs/INTEGRATION.md`, `docs/ACCEPTANCE.md` sind Nachschlagewerke; der aktuelle Gesamtstand steht in der Haupt-App unter `docs/NOW.md`.
- Dateninvarianten: konkreter Artikel und Produktversion, korrekte Händler-/Filialzuordnung, unverwechselbare Varianten/Packungen, mehrdeutige OCR/GTIN/SKU-Matches nicht als bestätigte Fakten buchen; private Bons/Preisbeobachtungen nicht öffentlich veröffentlichen.
- v1 `1.0.0-draft` bleibt unverändert, v1.1 nur unverbindlicher Draft. Original-Contract-Tests und Python-Referenzcode **erhalten**, keine parallele zweite Android-Datenbank oder OCR-Implementation.
- Bei ausdrücklich beauftragter Änderung: vorhandene Unit-/Vertragstests ausführen, genaue Änderungen/fehlende Nachweise dokumentieren, keine Fakten oder Rechte aus Modell-/Händlerbehauptungen erfinden.

Kein Schreiben in Haupt-App/andere Repos ohne ausdrücklichen neuen Nutzerauftrag.
