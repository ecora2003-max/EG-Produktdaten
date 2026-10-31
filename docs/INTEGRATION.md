# Codex-Anbindung: Produktidentität und Preisgedächtnis

**Vertrag:** EG-Architecture 1.0.0-draft, Git-Commit d22862739bd0e3ef8451ce029e54f7c33ee53e40; vendortes Schema: contracts/v1/contract.schema.json. **Runtime:** Python-Standardbibliothek als deterministische Offline-Referenz, später als reiner Kotlin-Kern zu übertragen. Kein Python-/Cloud-Laufzeitdienst in Android nötig.

## 1. Ein- und Ausgaben

### Produktkatalog

normalize_article(raw, source=None): Rohobjekt mit den Pflichtfeldern id, versionId, label und optional retailerId, retailerArticleId, gtin, foodTypeId, brandName, brandKind (MANUFACTURER/PRIVATE_LABEL/UNKNOWN), organic (true/false/null), attributes und quantity. quantity hat amount (Ganzzahl pro Einzelpackung), unit (g/ml/piece/portion), basis (NET/DRAINED/GROSS/PIECE/PER_PORTION/UNKNOWN), confirmed (bool) und optional packageCount. Kein generierter FoodType, GTIN oder Bio-Nichtstatus aus fehlender Angabe. EDEKA, Netto Marken-Discount und Penny werden über kleine konservative Eigenmarken-Namenslisten erkannt; Netto mit Scottie-Hund ist **ein anderer Händler**. Fremd-/Offlinekatalogdaten nur als vom Aufrufer bereitgestellter Snapshot; Rechte/Quelle unverändert führen. Ein Open-Food-Facts-Liveadapter wird nicht benötigt, da bereits in der App vorhanden.

### Produktmatching

find_candidates(query, catalog, aliases=[]): query benötigt retailerId; optional rawText, gtin, retailerArticleId, foodTypeId, requestId. catalog ist eine Liste obiger Artikel (mit stabilen Versionen). Ausgabe ist eine nach internem rankScore sortierte Liste von Payloads nach Architekturtyp product.match; enthält candidate, matchLevel, status, evidence, conflicts und die namespaced Erweiterung egProductdaten mit productId, versionId, rankScore, requiresPurchaseConfirmation=true. Confidence ist bewusst null; Punktestand ist keine kalibrierte Wahrscheinlichkeit. Mehrere plausible Produkte bleiben AMBIGUOUS, erwiesene Konflikte REJECTED. EXACT_SKU bezeichnet belegte Barcode-/Händler-SKU-Übereinstimmung und **noch keinen bestätigten Einkauf**. Auch 0 Treffer sind erlaubt. GTIN wird geprüft und für den Vergleich links auf 14 Ziffern aufgefüllt, die Originaldarstellung bleibt erhalten.

### Aliasentscheidungen

resolve_alias_decision(ledger, decision) ist eine reine Funktion mit neuer Ledger-Liste als Ergebnis. decision enthält decisionId, retailerId, rawText, confirmed=true, reason, decidedAt (ISO mit Zone), action=CONFIRM/CORRECT/REVOKE, expectedPreviousId sowie productId und versionId bei Bestätigung/Korrektur. Alte Entscheidungen bleiben unverändert; die aktuelle Blattentscheidung wird durch die Vorgänger-ID gefunden. Händlerwechsel, stale Version oder zwei aktive widersprüchliche Entscheidungen erlauben keinen automatischen Match. Gleiche decisionId und gleicher Inhalt sind idempotent; geänderter Inhalt löst ConflictError aus. Für Android bleiben die existierenden alias_decisions und RecognitionOperations.alias die **einzige** persistierte Quelle; das Ledger ist ein fachlicher Referenz-/Projektionsport.

### Bonzeilen

classify_receipt_line(line) liefert receipt.line-Payload mit unverändertem rawText. lineKind der App (FOOD, NON_FOOD, DEPOSIT, DISCOUNT, RETURN, UNKNOWN) wird gewahrt, sonst nur vorsichtig aus eindeutigen Schlüsselwörtern vorgeschlagen. Ein normales Warenwort wird ohne Prüfung nicht zu FOOD erklärt. Nur Cent-Ganzzahlen oder sicheres Dezimal-Preissuffix werden erkannt; 199A, negatives FOOD, Rückgeld und Summenzeilen nicht als gekaufte Lebensmittel verbuchen. Der Ausgangsstatus confirmed=false bleibt erhalten.

### Preisbeobachtungen

to_historical_price_observation(receipt, line, article) gibt {"observation":PriceObservation|null,"reason":Code|null} zurück.

receipt-Pflicht: purchaseId, receiptId, retailerId, purchaseConfirmed=true, confirmedAt als ISO-Timestamp mit Zone sowie purchaseAt mit Zone **oder** purchasedOn als genaues ISO-Datum. storeId optional. Bei nur Datum bleibt purchaseAt **null** und purchasedOn korrekt, statt eine Uhrzeit zu erfinden.

line-Pflicht: lineId, receiptId, retailerId, lineKind=FOOD, confirmed=true, productConfirmed=true, productId, versionId, unitsConfirmed=true, purchaseUnits als positive Ganzzahl, amountCents als tatsächlicher Waren-Positionsbetrag vor eindeutig zugeordnetem Rabatt, discountReconciled=true, amountExcludesDeposit=true. Optionale Sonderfelder: discountApplied, allocatedDiscountCents, unallocatedDiscount, depositPerUnitCents, gtin, storeId.

article muss zu bestätigten productId/versionId gehören. Bei unklarem Preis, unbekannter Stückanzahl, nicht zugeordnetem Rabatt, fehlender Deposit-Rechnung, unsicherer Identität, Retouren oder Pfandpositionen wird nur ein reason ausgegeben, nie eine Beobachtung. Ein unbestätigter OCR-Entwurf kann die Bestätigungsgates nicht passieren.

Bei Erfolg: Preis als Ganzzahl (amountCents − allocatedDiscountCents) / purchaseUnits **nur ohne Rest**. Sonderfall 0 Cents ist erlaubt und bleibt von unbekannt null verschieden. Pfand getrennt; priceKind=HISTORICAL_PAID, validFrom/validUntil=null, dataQuality=CONFIRMED, evidenceKind=USER_CONFIRMED_RECEIPT. Fehlt storeId, scopeType=UNKNOWN (nicht fälschlich STORE_CONFIRMED). Historische Produktversion und Kaufdatum bleiben als egProductdaten-Extension. Quelle des privaten Belegs wird nie veröffentlicht.

build_price_memory([{receipt,line,article},...]) erstellt deterministisch aus bestätigten Datensätzen eine eindeutige Beobachtung pro purchaseId+receiptId+lineId. Gleicher Retry/Scan erzeugt eine Beobachtung, separate echte Käufe mit unterschiedlichen purchaseIds erzeugen zwei. Inhaltlicher Konflikt bei derselben ID ist ein Fehler. apply_memory_correction(snapshot,event): confirmed=true, eventId, observationId, expectedRevision, decidedAt mit Zone, action=RETRACT/REPLACE. Für REPLACE sind die erneut aus **persistiert bestätigtem Ursprungskauf** projizierten Objekte receipt, line und article Pflicht; die Engine erzeugt das Ersatzpayload ausschließlich über den verifizierenden Preis-Builder. Ein zusätzliches replacement muss exakt übereinstimmen. Revision/Tombstone werden nur als reiner neuer Snapshot zurückgegeben; die tatsächliche persistierte Bestätigung und Transaktion liegen ausschließlich bei Codex.

as_contract(messageType,payload,createdAt,traceId) setzt den 1.0.0-draft-Umschlag. Die Schema-Tests nutzen das exakte vendorte Contract-JSON (Provenienz: Architekturcommit oben).

## Ergänzung: strengere Identitäts-/Korrektur-Gates

- `find_candidates` verknüpft händlergebundene Aliasbeweise über **(productId, versionId)**, niemals nur über eine mehrfach vorkommende Versionszeichenfolge. Eine bestätigte Altentscheidung wird nur mit ausdrücklich vom App-Katalog belegtem `currentVersionConfirmed=true` als `CONFIRMED_BY_USER` wiedererkannt; ohne aktuellen Versionsnachweis bleibt sie `AMBIGUOUS`. Diese Bestätigung ist ein Befund zur früheren Aliasentscheidung, **kein** Bezahl-/Bestandsnachweis.
- `apply_memory_correction` akzeptiert keine frei erfundenen `replacement`-Preis-Payloads. Bei `action=REPLACE` muss `event` vollständige, vom App-Adapter aus persistierten bestätigten Quellen gebildete `receipt`, `line`, `article` enthalten. Die Engine baut die neue Beobachtung erneut durch `to_historical_price_observation`, prüft die gleiche Positions-ID und ggf. die exakte Übereinstimmung mit einem zusätzlich gelieferten `replacement`. Bei unbestätigtem Kauf wird die Korrektur abgewiesen. Ein allein übergebenes `replacement` wird nicht übernommen.
- Kaufbestätigung darf einem bekannten Kaufzeitpunkt nicht zeitlich vorangehen; bei reiner Datumsangabe darf der Bestätigungstag nicht früher als das belegte Kaufdatum sein.

### Bon-Vorzeichen und Alias-Historie

- Ein explizites negatives OCR-Preissuffix wie `MILCH -1,99` bleibt **−199 Cents**, nicht +199. Bei negativem FOOD-Vorschlag wird die Kategorie auf UNKNOWN zurückgesetzt und eine Warnung erzeugt; RETOUR/Discount bleiben gesonderte Kategorien. Ohne Nutzerbestätigung keine Kauf- oder Preisbuchung.
- Die Alias-Ledger-Projektion verwirft unbestätigte/ungültige historische Entscheidungen und verweigert doppelte `decisionId` oder eine `expectedPreviousId`-Referenz über Händler-/Rohtextgrenzen. Ambige Legacy-Branches werden nicht still aufgelöst.
- `currentVersionConfirmed=true` muss aus der **aktuellen, versionierten App-Katalogprojektion** stammen. Nicht als pauschalen Default setzen, nicht aus OFF ableiten; bei fehlendem Nachweis bleibt eine frühere Aliasentscheidung AMBIGUOUS.
- Aliasentscheidungen und Händler-SKUs können optional an `storeId` gebunden sein. Ein filialgebundener Alias gilt ausschließlich bei identischer bestätigter Filiale, nicht bei unbekannter Filiale oder anderem Markt. Kettenweite Aliase bleiben separat; mehrere gleichzeitig passende Ketten-/Filialentscheidungen können AMBIGUOUS werden. `storeId` ist stets zusammen mit `retailerId` zu interpretieren. Die Kotlin-Projektion muss dieselben Filter- und Konfliktregeln übernehmen.

### Bereits geladene Open-Food-Facts-Datensätze (kein zusätzlicher Netzwerkzugriff)

`import_off_snapshot(snapshot, product_id, version_id, retailer_id=None, source=...)` übernimmt eine **vom Haupt-App-OFF-Adapter bereits empfangene** JSON-Produktantwort. `product_id` und `version_id` kommen aus dem Haupt-App-Katalog, nicht aus OFF. `source` enthält mindestens `origin`, `rightsStatus` (`UNVERIFIED` als sichere Voreinstellung), `dataQuality=SOURCED|UNKNOWN`, `observedAt` als ISO-Zeitstempel mit Zone. Eine behauptete bestätigte OFF-Quelle wird zurückgewiesen. Produktname/Barcode werden auf Konsistenz geprüft; Verpackungstexte wie `2x500 g` können als **unbestätigte** Mengenvorschläge übernommen werden (Mengenbasis `UNKNOWN`). Bio wird nur beim expliziten OFF-Label `en:organic` oder entsprechendem Bio-Tag vorgeschlagen; fehlende Kennzeichnung ergibt `null`, niemals `false`. Danach müssen App-Editor und Nutzer Angaben/Kauf gesondert bestätigen.

## 2. Anschluss an die bestehende Android-App (lesend geprüft am 31.10.2026)

1. RecognitionReader.review(scanId) liefert ReceiptScanView, OCR-Rohtext und ReceiptParser-Vorschläge; RecognitionReader.data()/snapshot() liefert versionierte Alias-/Produktdaten. Gtin.parse aus data.recognition.Identifiers bereits verwenden (UPC/EAN-Prüfung und 14-stelliger Lookup-Key). **Keine** neue Kamera, ZXing- oder ML-Kit-Implementierung.
2. Produkt-Versionen aus dem vorhandenen Katalog nur als read-only Snapshot in den Matcher projizieren. In Compose die Kandidaten, Konflikte und unbekannten Felder zur **editierbaren** Entscheidung anzeigen. Bestehende RecognitionReader.match und alle Aliasversionen respektieren. Nutzervotum über RecognitionOperations.alias mit vorhandener erwarteter Version/Operation speichern, nicht durch das Modul direkt schreiben.
3. Den tatsächlich bezahlten Einkauf ausschließlich über FoodStore/PurchaseOperations.save(confirmed=true,scanId,expectedCatalog) oder confirmReceipt speichern. receipt_scans sind Entwürfe; receipt_scan_resolutions verhindern dieselbe Scanübernahme unter Parallelität. Ohne PurchaseEventEntity und gültigen Zustand **keine** bestätigte Preisbeobachtung.
4. Nach dem Kauf aus **persistierten** ReceiptEntity, ReceiptLineEntity, PurchaseEventEntity und überprüften Produkt-/Mengen-/Rabattentscheidungen den Preis-Builder mit eindeutigen IDs aufrufen. ReceiptEntity.purchasedOn enthält nur einen Tag; daher purchasedOn statt erfundener Kaufuhrzeit mappen. Die aktuell vorhandenen App-Felder belegen Rabattzuordnung, Ausschluss von Pfand und bestätigte Verkaufseinheiten **noch nicht generell**. Codex muss diese Prüfwerte/Entscheidungen als versioniertes lokales UI-/Datenmodell hinzufügen oder den Preis bewusst ungelöst lassen. Nicht anhand der Bon-Gesamtsumme rabattierte Einzelpreise schätzen.
5. Beobachtung im selben lokalen Transaktions-/Idempotenzrahmen an Kauf und positions-/versionsgebundene bestätigte Entscheidung knüpfen. observationId unique; Revision/Tombstone und Source/Date/Scope/Unknown-Felder unverändert speichern; Rücknahmen/Stornos müssen die historische Preisbeobachtung revidieren. Keine extra Zahlungs-, Bestands- oder Verzehrbuchung. Preisgedächtnis separat der Vergleichsengine als **historische, nicht aktuelle** Preisquelle übergeben.
6. Nach Port/Room-Migration alle Python-Testfälle als deterministische Kotlin-JVM-Tests spiegeln und Schema-JSON prüfen; zusätzlich vorhandene RecognitionParsingTest, RecognitionLifecycleTest, RecognitionDatabaseTest, PurchaseOperations-/Migrationstests ausführen. Geräte-ML-Kit bleibt Codex-Aufgabe.

## 3. Exakte Kotlin-Portierungsregeln

- Python int → Kotlin Long mit Overflow-Prüfung; keine Floating-Point-Preise. Decimal für g/ml-Konversion → BigDecimal + longValueExact(), keine Stückgewichtserfindung.
- ISO-Zeitpunkt → OffsetDateTime.parse, bestätigtes Kaufdatum → LocalDate.parse; keine Normalisierung unbekannter Uhrzeit zu Mitternacht.
- NFKC-Text mit Unicode Normalizer und Locale.ROOT in Kleinschreibung; OCR-Rohtext niemals überschreiben.
- GTIN nach App-Gtin.parse und kanonisch mit führenden Nullen auf 14 Stellen; Händlerartikelnummer **niemals** als Barcode behandeln.
- Deterministische Price-ID: SHA-256 über UTF-8 von purchaseId + U+001F + receiptId + U+001F + lineId; erstes 32-stelliges Hex-Präfix, vorangestellt receipt-. Unbekannte/von der App nicht bestätigte Identitäten nicht künstlich erzeugen.
- Unveränderliche data classes; Alias- und Preis-Revisions-CAS nur innerhalb FoodStore Room-Transaktion und mit Unique-Indizes. Reihenfolge: score absteigend, produktId und versionId aufsteigend. Fachvertrags-Enums und nullable Werte beibehalten.
- Python und Kotlin müssen gleiche synthetische Fixture-Ergebnisse erzeugen. Vergleichsengine ist Empfänger, nicht direkter SQL-Schreibzugriff.

## 4. Quellen, Grenzen und Sicherheit

Eigenmarkenlisten sind **nur** konservative Indizien; nicht jedes Produkt wird erkannt. Externe Daten dürfen als Snapshot importiert werden, wenn Recht/Quellstatus explizit eingetragen ist. Keine Live-Händleranbindung, keine Lizenzzusage, keine echten Kassenbons oder Tokens im öffentlichen Repo. Der reine Python-Kern benötigt keine externen Dienste; Android-Port und reale Geräteeinbindung sind **nicht** durch Python-Tests verifiziert.