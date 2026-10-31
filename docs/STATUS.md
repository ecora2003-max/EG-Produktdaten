# Status und Abnahme — EG-Produktdaten

**Stand:** 31.10.2026. **Fachmodul abgeschlossen: READY_FOR_INTEGRATION (offline verifizierte Referenzengine).** **Nicht INTEGRATED.** Die Android-Portierung, lokale Room-/FoodStore-Einbindung, App-Regression und Hardwaretests sind ausschließlich Aufgabe von Codex.

## Verifizierter Stand

- Letzter fachlicher Codecommit: [`30f36e7cdbee568f4e122db8689c57b917d8f4ab`](https://github.com/ecora2003-max/EG-Produktdaten/commit/30f36e7cdbee568f4e122db8689c57b917d8f4ab). Enthält Unicode-/Leerzeichen-Negativpreis-Regressionskorrektur; baut auf `ecf569fa263f39ca852d5da40840e420690a2ca1` (Händler-/Filialbindung für Aliasbeweise und Händler-SKUs) sowie auf `d41b3ec0e602d90e9030f2816a503aa3f2e192cc` (OCR-Vorzeichen, Alias-Ledger-Integrität) und vorherigen Commits `9668118279d99e7748fb2d178fd244692431a0d3` (OFF-Adapter), `1335aebe695ce02c7e29c782d2650fb98f386039` (bestätigte Korrektur), `77d91ed8c7626ca10114ef7f3c75673148d15d9b` (Aliasidentität) auf.
- **Tatsächlicher GitHub-Actions-Lauf:** [41220106489](https://github.com/ecora2003-max/EG-Produktdaten/actions/runs/41220106489), Code-SHA `30f36e7cdbee568f4e122db8689c57b917d8f4ab`. **105 Tests bestanden, 0 fehlgeschlagen, 0 übersprungen**, `OK` im vollständigen Joblog. Der anschließende `compileall`-Schritt war erfolgreich. CI-Job `124592702975` auf Python 3.11.
- **Reproduktion:** `python -m pip install -r requirements-dev.txt && python -m unittest discover -s tests -p 'test_*.py' -v && python -m compileall -q eg_productdaten tests`. CI: `.github/workflows/tests.yml`, Job `tests`, Timeout 8 Minuten.
- **Gemeinsame Architektur:** EG-Architecture `1.0.0-draft`, zuletzt gelesen bei Commit `d22862739bd0e3ef8451ce029e54f7c33ee53e40`. Vendortes `contracts/v1/contract.schema.json` hat dieselbe Blob-SHA `bedde4677342817fe6b883962c8dfbbd60100072` wie der aktuelle Architekturvertrag. JSON-Schema Draft 2020-12 + FormatChecker wird in Tests verwendet.
- **Testdaten:** ausschließlich synthetische Artikel, Bonzeilen, Händler-/Produkt-/Kauf-IDs und Offline-OFF-Snapshots in `tests/test_engine.py` und `examples/demo.py`; keine echten Belege, Zugangsdaten oder personenbezogenen Daten.

## Nachweismatrix zu docs/ACCEPTANCE.md

| Bereich | Verifiziertes Verhalten |
| --- | --- |
| GTIN | EAN-8, UPC-12, EAN-13, GTIN-14, führende Nullen, 14-stelliger Lookup-Key, Prüfziffer; falsche Prüfziffer, Nicht-ASCII, Nullcode und Händler-SKU abgewiesen |
| Produktidentität | Händler-SKU nur im Händlerkontext; Packungs-/Variantenkonflikte, Bio true/false/null, Eigenmarken EDEKA/Netto Marken-Discount/Penny und Scottie-Trennung; keine automatisch erfundene Produktwahl |
| Alias | Bestätigung, Wiederholung, Korrektur, Rücknahme, CAS, konkurrierende Heads, Cross-Product-/Version-Verwechslung, fehlender aktueller Versionsnachweis, Händler- und Filialbindung; doppelte IDs, Cross-Merchant-/Cross-Store-Referenz und unbestätigte Ledger-Einträge abgewiesen |
| Bonpositionen | 5 typische und 5 schwierige synthetische Positionen, FOOD nicht ohne Beweis, Non-Food/Pfand/Rabatt/Retoure/Storno/Rückgeld, OCR-Fehler `199A`, negatives Preissuffix und erhaltenes Rohtextfeld |
| Historischer Preis | Ausschließlich bestätigter Kauf + bestätigte FOOD-Position + Produktversion + Verkaufseinheiten + Rabatt-/Pfand-Abgleich; null/0 korrekt, Kaufdatum und Filialkontext ohne Erfindung, keine aktuelle Preisbehauptung |
| Deduplizierung/Korrektur | Mehrfach-Scan idempotent, echte verschiedene Käufe getrennt, abweichender Retry konfliktbehaftet, Tombstones/Revisionen und erneut bestätigte Ersatzbeobachtungen |
| Menge | Stück-/Gebindepreis nur bei belegter Einheitenzahl, keine Rest-Cent-Rundung, keine kg-/l-Umrechnung aus unbestätigter Netto-/Abtropfbasis |
| OFF-Import | Bereits vorhandener OFF-Snapshot als unbestätigter Vorschlag mit Herkunft, Rechte-/Qualitätsstatus, GTIN-Abgleich, Bio-Tag, Packungsangabe und unbekannter Mengenbasis; keine Live-Abhängigkeit |
| Vertrag | `product.match`, `receipt.line`, `price.observation` einschließlich Source/Date/Scope, nullable Werten, bekannten 0-Werten, ungültigen Pflichtfeldern formal per Schema geprüft |
| Sicherheit | Reiner, deterministischer Python-Kern; kein Netzwerk/OCR/Kamera/Room/DB-Schreiben, kein Bestands-/Zahlungsereignis, Eingaben unverändert |

## Übergabe an Codex und bewusst offene Integrationsaufgaben

1. `docs/INTEGRATION.md` beschreibt API, Fehlermodelle, ID-Hashing, Kotlin-Typen, Room-/FoodStore-Transaktionsgrenze, RecognitionReader/ReceiptParser-Anbindung und Testspiegelung. Der Python-Fachkern ist **kein Android-Binary**. Codex muss Kotlin-Port und JVM-/App-/Migration-/Gerätetests selbst nachweisen.
2. `currentVersionConfirmed` ist eine vom App-Katalog belegte Versionsentscheidung, **keine** Default-Eigenschaft externer Produkte. Ohne Nachweis bleibt ein historischer Alias unbestätigt für die aktuelle Variante.
3. Die App muss Rabattzuordnung, bestätigte Verkaufseinheiten und Pfandausschluss pro Position verlässlich erfassen. Fehlt ein Beleg, bleibt der Preis **unresolved**, niemals als `HISTORICAL_PAID` gespeichert.
4. OFF-/Händlerdaten nur als zulässige, nachvollziehbare Snapshots. Es wurde **kein** Live-API-/Händlerabdeckungs- oder Lizenznachweis beansprucht. Preisgedächtnis ist historisch, keine Aussage über heutige Filialpreise.
5. Die Architektur ist noch `1.0.0-draft`; bei neuer freigegebener Vertragsversion sind Schema- und Integrationsregressionen erneut erforderlich. Ein produktives Daten-/Bestands-/Kaufereignis darf ausschließlich die Haupt-App bestätigen und schreiben.

**Fazit:** Alle **modulspezifischen Offline-Abnahmekriterien** sind anhand der 105 ausgeführten automatisierten Tests einschließlich Vertragstests und dokumentierter Android-Adaptergrenze erfüllt. Keine noch offene Aufgabe liegt im erlaubten Schreibbereich des Produktdaten-Fachmoduls; die verbleibenden Arbeiten sind Integrations- und Freigabegates anderer Eigentümer. Keine direkte Änderung an Architektur, anderen Modulen oder Haupt-App vorgenommen.
