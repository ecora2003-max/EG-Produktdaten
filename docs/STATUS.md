# Status und Abnahme — EG-Produktdaten

**Stand:** 31.10.2026. **Status: READY_FOR_INTEGRATION (offline verifizierte Python-Referenzengine), NICHT INTEGRATED.** Freigabe gilt nur für den unabhängig geprüften Fachkern und seine dokumentierten Datenschnittstellen. Keine Android-App- oder Hardwareintegrationsfreigabe.

## Reproduzierbarer Nachweis

- Gemeinsamer Fachvertrag: EG-Architecture **1.0.0-draft**, zuletzt gelesener Commit `d22862739bd0e3ef8451ce029e54f7c33ee53e40`; exakte Vertrags-Schema-Testkopie in `contracts/v1/contract.schema.json`.
- Fachimplementierung: Commit `fb7314b747018fcdf57bc2dc234d3496d69b6c82`. GitHub-Actions-Lauf [41219124572](https://github.com/ecora2003-max/EG-Produktdaten/actions/runs/41219124572), **80 Tests bestanden, 0 fehlgeschlagen, 0 übersprungen**; Syntax/Compile-Schritt bestanden.
- Nach anschließender versionsbezogener Alias-Regressionskorrektur: Commit `a0defadb8359239780358952eebcd2f572db82fd`; GitHub-Actions-Lauf [41219251188](https://github.com/ecora2003-max/EG-Produktdaten/actions/runs/41219251188), **81 Tests bestanden, 0 fehlgeschlagen, 0 übersprungen**; Python 3.11.17 und Compile-Schritt bestanden. Lauf-Logs wurden tatsächlich gelesen.
- Reproduktion: `python -m pip install -r requirements-dev.txt && python -m unittest discover -s tests -p 'test_*.py' -v && python -m compileall -q eg_productdaten tests`; dieselben Befehle in `.github/workflows/tests.yml` (getrennte Schritte).
- Synthetische Daten: `tests/test_engine.py`, `examples/demo.py`. Keine realen Bons, Anmeldedaten oder Cloud-Dienste.
- Nachweisgrenze: JSON-Schema-Test (Draft 2020-12 mit FormatChecker), reiner Python-Referenzkern; keine Gerätemessung oder Live-Händlerdaten.

## Abnahmematrix zu docs/ACCEPTANCE.md

| Bereich | Testergebnis / Nachweis |
| --- | --- |
| GTIN | EAN-8, UPC-12, EAN-13, GTIN-14, führende Nullen und Android-kompatible 14er-Kanonisierung; falsche Prüfziffer, Nullcode, Nicht-Ziffer, Händler-SKU abgewiesen |
| Produkt | Varianten-/Packungs- und Bio-Widerspruch, Null-Bio, Eigenmarken EDEKA/Netto Marken-Discount/Penny, fremde Händler und Katalog-Provenienz |
| Bonalias | Nur explizite Händler-/Version-Bestätigung, idempotenter Replay, Händlerwechsel, Korrektur, Revokation, stale/CAS, zweideutige Heads; Regression für mehrere Versionen im Katalog |
| Bonposition | 5 typische und 5 schwierige synthetische Rohzeilen automatisiert; Pfand, Non-Food, Rabatt, Retoure/Storno, Rückgeld, OCR-Fehler 199A; Originaltext erhalten |
| Preisgedächtnis | Nur bestätigter tatsächlicher Kauf+Produktversion+Position+Verkaufseinheiten+Preis-/Rabatt-/Pfandabgleich → HISTORICAL_PAID; unbestätigter Entwurf abgewiesen |
| Duplikate | idempotente Wiederholung, zwei echte Käufe separat, widersprüchlicher Replay löst ConflictError aus |
| Zeit/Filiale | validiertes zonenbehaftetes Datum oder reines Kaufdatum ohne erfundene Uhrzeit; keine bestätigte Filiale ohne storeId; abweichende Händler/Daten/Versions-IDs abgewiesen |
| Menge/Rabatt | Mehrfach-Gebinde, NET-Basis, inkompatible Packung, nichtteilbarer Stückpreis als ungelöst; zugeordneter Discount; unklarer Rabatt/Pfand explizit ungelöst |
| Fachvertrag | product.match, receipt.line, price.observation inkl. null/0 als JSON Schema erfolgreich; ungültige/fehlende Pflichtfelder formal zurückgewiesen |
| Sicherheit | reine Funktionen ohne IO/Netzwerk/Room; Test prüft Input-Immutabilität, keine tatsächliche Buchung; nur synthetische Fixture |

## Schnittstellen und Integrationsgrenze

Alle im Entwicklungsmandat geforderten Funktionen liegen ausführbar in `eg_productdaten/core.py` vor. Vollständige Portsignaturen, bestätigungsbedürftige Felder, idempotente Beobachtungs-IDs, Fehler-Codes, Barcode/ReceiptReader-Anschluss und genaue Kotlin-/Room-Portierungsregeln: `docs/INTEGRATION.md`. Die App besitzt bereits OCR, Barcodeprüfer, `alias_decisions`, `receipt_scans` und Kauf-Transaktionen. **Nichts davon wurde ersetzt oder verändert.** Nutzerbestätigungen bleiben alleinige Wahrheit der Haupt-App.

## Offene / bewusst nicht behauptete Nachweise

1. Kein nativer Kotlin-/Android-Port, keine Integration in Room/FoodStore und keine Geräteprüfung; Codex muss diese separat durchführen. `READY_FOR_INTEGRATION` ist gerade **nicht** `INTEGRATED`.
2. Das aktuelle App-Schema belegt die erforderlichen Bestätigungen zu pro Position zugeordneten Rabatten, Verkaufs-Packungsanzahlen und Pfandausschluss nicht in allen Fällen; Codex muss zusätzliche bestätigte Datenfelder/Entscheidungen in seiner App speichern oder die Beobachtung als ungelöst belassen.
3. Katalog-Import ist eine reine Snapshot-Schnittstelle, kein geprüfter OFF-/Supermarkt-Liveadapter. Historische Bonbeobachtungen begründen keine aktuellen Kettenpreise und kein allgemeines Datenlizenzrecht.
4. Match-Scores sind heuristisch und nicht probabilistisch kalibriert; ungeprüfte Katalogfelder, Mengen und Bio bleiben unbekannt. Korrigierte historische Beobachtungen nur nach erneuter Beleg-/Versionsbestätigung durch Codex persistieren.
5. Keine private Nutzer-/Boninformation und keine kostenpflichtige Pflicht-API.

**Für automatische Wiederaufnahme:** Bei späterer Architekturversion den aktuellen Contract, dieses Dokument und `docs/ACCEPTANCE.md` vergleichen; unveränderte, erfolgreich getestete Module nicht unnötig neu bauen. Bei tatsächlich neuen Problemen erst regressionsreproduzierenden Test hinzufügen, Code korrigieren, CI nachweisen und diesen Status mit SHA/Testergebnis fortschreiben. Eine produktive Integration nie ohne Codex-Prüfung behaupten.
