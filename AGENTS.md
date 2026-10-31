# Verbindlicher Auftrag – Chat 3 / Produktidentifikation und Preisgedächtnis

## Rolle und Grenze
Du entwickelst ein eigenständiges, testbares Produkt zur Erkennung/Verknüpfung von Produktidentitäten, Marken- und Bio-Merkmalen, Händler-SKUs, GTIN und Bontexten sowie zur Umwandlung **bestätigter** Belegpositionen in datierte Preisbeobachtungen.

**Einziges Schreibziel:** `ecora2003-max/EG-Produktdaten`. **Nur lesen**, niemals bearbeiten: `EG-Architecture`, alle anderen Modulrepos und das private Hauptrepo `ecora2003-max/Ernaerungsgedaechnis` (vom Nutzer auch „Ernährungsplan“ genannt). Keine GitHub-Issues/PRs/Branches dort verändern. Die Integration schreibt ausschließlich Codex.

## Vor Arbeitsbeginn lesen
`EG-Architecture/README.md`, `docs/MASTER_ARCHITECTURE.md`, `docs/DOMAIN_MODEL.md`, `docs/INTEGRATION_AND_GOVERNANCE.md`, `contracts/v1/`. Optional lesender Blick auf die bestehende App-Bon- und Barcode-Erkennung: **nicht neu implementieren**.

## Verbindliche Qualität
- **Nach jeder implementierten Funktion und jeder verhaltensändernden Änderung Tests ausführen.** Positiv-, Negativ-, Konflikt-, Null-/Unbekannt-, Duplikat- und Regressionsfälle.
- Keine automatische Speicherung aus OCR-Vermutungen; bestätigte Aliase mit Händler-/Variantenbindung, Geschichte und Korrekturmöglichkeit.
- Kein reales Benutzer-/Bon-/Gesundheitsdatum in dieses öffentliche Repo, GitHub Actions oder Beispielpayloads.
- Ohne nachgewiesene Funktionalität nur `PROTOTYPE`/ `PARTIAL`; `READY_FOR_INTEGRATION` erst nach `docs/ACCEPTANCE.md`. Nachweisen mit Commit, Befehl, Testergebnis. `INTEGRATED` nur Codex.
- Bei fehlenden oder falschen Feldern im gemeinsamen Vertrag **Änderungsvorschlag im eigenen Repo**, keine direkte Änderung am Architektur-Repo.

Lies `docs/DEVELOPMENT_MANDATE.md`, `docs/ACCEPTANCE.md` und `docs/INTEGRATION.md` vor Umsetzung.
