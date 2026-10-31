# Entwicklungsmandat – Produktidentität, Bon-Aliase und Preisgedächtnis
**Rolle:** Produktdaten-Chat / eigenständiger Zulieferer

## 1. Ziel
Eine offline testbare, später Android-fähige **Matching- und Preisbeobachtungs-Engine**, die generische FoodTypes, konkrete Marken-/Eigenmarkenprodukte, Bio-Status, GTIN, Händlerartikelnummern, Händler-Filialkontext und Bon-Kurzbezeichnungen **ohne Identitätsverlust** verknüpft. Aus verifizierten Käufen entsteht ein lokales, zeitlich korrektes Preisgedächtnis.

## 2. Bereits im Hauptrepo vorhanden – nur lesen
In `Ernaerungsgedaechnis` existieren laut Übergabe (30.10.2026) Room-Schema 7, 35 Tabellen, barcode-/GTIN-Erkennung mit Prüfziffer, OFF-Daten als editierbare Vorschläge, ML-Kit-Bon-OCR, `receipt_scans`, `receipt_scan_resolutions`, versionsgebundene `alias_decisions` und kontrollierte Käufe. **Nicht** eine weitere produktive Beleg-Datenbank oder OCR-App bauen. Codex integriert deinen reinen Erkennungskern über die vorhandenen Eingabemodelle/FoodStore-Schreibgrenze. Keine Produktivdatenzugriffe, keine Änderungen im Hauptrepo.

## 3. Öffentlicher Datenvertrag
`FoodType` ist nicht `Product`; `Product` ist nicht `RetailerArticle`; `GTIN` ist nicht gleich `retailerArticleId`; `ReceiptAlias` ist nicht gleich bestätigte Produktidentität. `organic=true/false/null` nur auf Grundlage geeigneter Beweise. `brandKind=PRIVATE_LABEL/MANUFACTURER/UNKNOWN`. Varianten, Roh-/Abtropfgewicht, Gebinde und Mengenbasis explizit.
Abfragen dürfen relevante Felder auch ohne Treffer zurücklassen – keine erzwungene Produktwahl. Produktmerkmale wie Bio, vegan, natur, gezuckert, TK/frisch, Sorte sind potentiell vergleichsrelevant.

## 4. Kernfunktionen – Lieferumfang
1. **Produktstandardisierung:** GTIN/UPC/EAN-Kanonisierung ohne führende Nullen zu verlieren, Daten-/Händler-SKU-Identitäten, Markeneigenschaft, FoodType-Hierarchie, Produktvarianten, Menge und Basiseinheit. Prüfsummen und Mengenbasis nachvollziehbar.
2. **Kandidatenfindung:** Bon-Zeile, optional EAN, Händler-SKU, Händler-/Markt-ID, Einzelpreis/Menge → Liste rankbarer Produktkandidaten mit **Erklärungen**, Matchstufe und Konflikten. Zusätzlich Matching aus allgemeinen Angebots-/Produktkatalogdaten.
3. **Alias-Lernen:** Nutzerbestätigte `ReceiptAlias → spezifische Produktidentität/Artikelversion` mit Händlerbindung und Gültigkeits-/Versionskontext; mehrdeutige Identitäten, Rücknahme und Korrektur. **Nie** ein Modellvorschlag allein als Bestätigung.
4. **Bonpositions-Qualifizierung:** Rohtext erhalten; Kategorisierung FOOD, NON_FOOD, DEPOSIT, DISCOUNT, RETURN, UNKNOWN mit überprüfbarer Unsicherheit. Position, Menge, Packung, Grundpreis nur bei ausreichender Information; bei Rabatt/Pfand keine Doppelzählung.
5. **Preisgedächtnis-Builder:** Aus **nur bestätigten** bezahlten, eindeutig zugeordneten Bonpositionen `price.observation` mit `HISTORICAL_PAID`, Händler/Filiale, Datum, korrekter Menge/Preis und Quellenstatus erzeugen; unklare Rabattzuordnung bewahrt unklaren effektiven Preis. Unbestätigte OCR-Werte niemals als Preisbeobachtung ausgeben.
6. **Import/Quellen:** OFF-Produktdaten, zulässige Händler-Produktkataloge und optionale historische externe Quellen einlesen können, nicht voraussetzen. Quelle/Lizenz/Qualität/Deduplikation dokumentieren. Eigenmarken EDEKA/Netto/Penny besonders im Fokus, ohne andere Artikel auszulassen.
7. **Export/Adapter:** Deterministische, typisierte `product.match`-, `receipt.line`- und `price.observation`-Outputs kompatibel mit `EG-Architecture/contracts/v1`. Nullwerte/unbekannt beibehalten.

## 5. Konkrete fachliche Sonderfälle
- Bonname `MILCH 1L` kann mehrere Sorten/Marken bedeuten: **kein** sicherer Match.
- Eine Händlerartikelnummer ist nur im Händlerkontext stabil; eine SKU darf nicht als EAN fehlinterpretiert werden.
- Gleicher Barcode kann Gebindevariante, Artikeländerung oder Konflikt zeigen: nicht auf falsches Produkt „letzte Antwort gewinnt“.
- Artikel-Neuversionen: bestätigte Zuordnung zu historischer Version bleibt historisch; spätere Namen/Nährwerte ändern alten Einkauf nicht.
- Bon-Zwischensumme, tatsächlich gezahlter Gesamtbetrag, Positionen, Rabatte und Pfand bleiben unterschiedliche Zahlen. Non-Food zählt ggf. zu Ausgaben, aber nicht zu Lebensmittelbestand/Nährwert.
- Papierbon kann Kauf-/EAN-Informationen **nicht** enthalten; kein GTIN ohne tatsächlich bekannten Barcode ableiten.
- Preisbeobachtung stammt aus Kauf **zum damaligen Zeitpunkt**, keine Zusage über heutige Regalpreise. Doppelte Scans/Retry dürfen Preisgedächtnis nicht verdoppeln.
- Keine autonome Lagerbuchung; Bestandszugänge und Lebensmittelsicherheit bleiben eigene, bestätigte App-Transaktionen.

## 6. Schnitt zum Einkaufs- und Preisdatenmodul
Preisdaten liefert katalog- oder angebotsseitige Artikel und zeitbezogene Preise. Produktdaten liefert Zuordnungskandidaten und bestätigte Preisbeobachtungen aus tatsächlichen Käufen. Einkaufsintelligenz entscheidet über Vergleichbarkeit und günstigere Alternativen mit festem Preis-Snapshot. Der Produktdatenchat implementiert **kein Ranking zu „wo ist es günstiger“**; nur Produktmatch-Evidenz.

## 7. Technisches Design
Trenne `normalize`, `extractCandidates`, `rankAndExplain`, `proposeAlias`, `makePriceObservation` und `serializeToContract`. Kern-Funktionen rein und deterministisch, ohne Netzwerk/Android/UI/Room. Wähle eine Android-kompatible oder leicht portierbare Technologie; erkläre den exakten Anpassungsaufwand. Externe Daten sind optionale Adapter; ein voll offline laufender Testmodus ist Pflicht.

## 8. Nicht Teil des Auftrags
Keine eigene Camera-/OCR-App, keine autonomen Live-Kassen- oder Händlerkontozugriffe, keine Arbeit an Hauptrepo/Architekturrepo, keine automatisierten Personal-Datenuploads, keine vollständige globale Produktdatenbank als vorgetäuschte Liefergarantie.

## 9. Übergabe
Quellcode, APIs, Daten-/Konfliktmodelle, Beispiel-Fixures, Tests, genaue Abnahmematrix, Update-/Versionsregeln, Android-Mapping-Hinweise, rechtliche Datenherkunft sowie `docs/STATUS.md`. Definiere, wann eine `PriceObservation` von historisch belegt vs. unsicher ist.
