# Testpflicht und Definition of Done – Produktdaten

**Immer testen:** nach jeder neuen Matching-Regel, Aliasänderung, Bonklassifikation, Datenimport, Preisnormalisierung und Versionsänderung die betroffenen automatisierten Tests sowie Regression ausführen. Jeder Statusbericht: Datum, SHA, Befehl, Anzahl grün/rot/übersprungen, verwendete synthetische Fixtures, offene Fälle.

## Pflicht-Testfälle
| Bereich | Positiv | Negativ/Grenzfall |
| --- | --- | --- |
| GTIN | EAN8/12/13/14 und führende Nullen korrekt | falsche Prüfziffer, verwechselte Händler-SKU |
| Produkt | richtige Variante und bekanntes Bio | Bio unbekannt, ähnlich lautende falsche Variante |
| Bonalias | gleiche bestätigte Händler-/Artikelversion wiedererkannt | gleiche Kurzbezeichnung in anderen Märkten, rückgenommene/mehrdeutige Zuordnung |
| Bonposition | Lebensmittel, Pfand, Non-Food, Rabatt separat | Rückgeld, Storno, OCR-Preis `199A`, Mengenfehler |
| Preisgedächtnis | bestätigter Kauf → genau eine historische Preisbeobachtung | OCR-Entwurf/erwarteter Kauf erzeugt **keine** |
| Mehrfachkäufe | zwei echte gleiche Käufe einzeln bestätigt | doppelt verarbeitetes Bild / Retries ohne doppelte Beobachtung |
| Datum | Kaufdatum/Filiale korrekt | ohne Datum/Markt keine falsche Tages-/Filialbehauptung |
| Menge | kg/g/l/ml nur bei nachweisbarer Basis | Stück ohne Gewicht, Füll- statt Abtropfgewicht |
| Export | Vertrags-JSON mit Beleg/Quelle/Status | unbekannte Pflichtwerte nicht durch Null ersetzen |
| Sicherheit | rein offline, synthetische Quellen | keine produktiven Daten/Secrets, keine direkte DB-Mutation |

## Mindestfunktion vor `READY_FOR_INTEGRATION`
- Parser/Matcher und Alias-Entscheidung **in ausführbarem Code** implementiert, kein bloßes Konzept.
- Für mindestens fünf typische und fünf schwierige synthetische Bonpositionen korrekte Match-/Konflikt-Ausgabe automatisiert nachgewiesen; zusätzlich Händlerwechsel, Bio-unbekannt, zwei plausible Kandidaten, Storno, Discount und Retoure.
- Preis-Builder erzeugt **nur** aus bestätigtem Kauf gültige `HISTORICAL_PAID`-Beobachtungen; Double-Count-Schutz und eindeutige Mengenbasis getestet.
- Inputs/Outputs gegen die aktuelle Vertragsversion geprüft, inklusive `null`/0 und Source/Date/Scope.
- Integrationsschritt an bestehende App-OCR/FoodStore konkret dokumentiert, jedoch keinerlei eigenständiger produktiver Kauf gebucht.
- Testlog + Befehle + Codeversion + bekannte Grenzen im Repo. Ohne Testbericht nur `PROTOTYPE`.
- `READY_FOR_INTEGRATION` heißt **nicht**, dass Codex App- und Gerätetests schon ausgeführt hätte.

## Nicht akzeptieren
Händlerunabhängige Kürzel als eindeutige Produktzuordnung; still erfundene EAN/GTIN; frei geschätzte Bonpreise als bezahlt; stilles Überschreiben alter Produktversionen; OCR-Text ohne Bestätigung als Bestand; zweite tatsächliche Ausgabensumme; Verwendung echter Belegdaten in öffentlichem Repo.
