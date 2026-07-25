# Congress Disclosure Business and Technical Assessment

Date: 2026-07-26 HKT

Status: House bounded live adapter and v2 ingestion complete offline; production
release and Senate adapter pending

## Business meaning

Congress Periodic Transaction Reports disclose reportable purchases, sales and
exchanges by a filer, spouse or dependent child. They are not real-time order
flow. Official Senate guidance states that a PTR is due no later than 30 days
after written notification and never later than 45 days after the transaction.

SmartFlow therefore treats Congress data as delayed actor evidence:

- preserve transaction date, notification date and filing date separately;
- preserve the disclosed amount range, never convert it to a midpoint;
- preserve the owner code because the asset may belong to the filer, spouse,
  dependent child or jointly;
- count a household/filer once across repeated rows and reports;
- rank newly disclosed activity for follow-up while displaying its latency; and
- never describe a disclosure as a live trade, exact amount or proven alpha.

## Official sources

### House

- Year index: `https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.zip`
- PTR PDF: `https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc_id}.pdf`
- The year archive contains official XML/TXT report metadata; `FilingType=P`
  identifies Periodic Transaction Reports.
- Transaction details remain in individual PDFs.

The current parser reads the official index XML and PDF word coordinates. It
fails closed on malformed rows, dates, amounts or identity fields. It preserves
both disclosed ranges and occasional exact amounts. It extracts a ticker only
when the report discloses one; it does not infer a ticker from an asset name.

Some official House reports are image-only scans with no text layer. SmartFlow
preserves the exact PDF and creates a non-directional `unparsed_document`
warning. It does not treat the document as empty, attempt unreliable implicit
OCR, or infer a transaction from the image.

### Senate

- Public entry: `https://efdsearch.senate.gov/search/home/`
- Access requires a user to acknowledge statutory prohibited uses before search.
- Reports may be posted after filing and transaction disclosure itself may lag.

SmartFlow must not automate acceptance of the Senate acknowledgement. A live
Senate adapter needs a separately reviewed session/access method that preserves
the user's personal, non-commercial use and does not bypass the access gate.

## Legal/use constraint

The official House and Senate notices prohibit use of financial disclosures for
unlawful purposes, most commercial purposes, credit-rating decisions and
solicitation. SmartFlow's approved use is the owner's personal research.

If SmartFlow becomes a client product, paid service or commercially distributed
dataset, Congress ingestion must stop until legal/licensing review confirms that
use. Public availability is not a redistribution licence.

## Implemented v2 contract

- `source=congress`
- `event_type=congress_periodic_transaction`
- `action=purchase|sale|exchange`
- `execution_status=reported`
- one event per official report row
- raw report identity is House `DocID`; normalized identity is chamber + DocID + row
- stable actor identity uses member name plus state/district, not DocID
- disclosed lower/upper amount remains in attributes; `value` stays null
- missing ticker is a warning and cannot enter ticker-level cross-source ranking
- image-only PDF is a warning event requiring OCR and has no direction/ticker
- parser version: `congress-house-ptr-v1`

## Acquisition and raw evidence controls

- HTTPS is restricted to `disclosures-clerk.house.gov`.
- Redirects are disabled and rejected.
- ZIP/PDF content type, magic bytes, `Content-Length`, streamed body size and
  exact expected ZIP member are bounded and validated.
- Each official PDF is stored byte-for-byte in base64 inside immutable raw
  evidence with a separate PDF SHA-256.
- Parser/schema failures preserve the PDF before recording degraded health.
- One bounded batch creates one aggregate collector outcome; a per-document
  failure cannot be hidden by later successes.
- Successful reruns are idempotent.

## Latest live disposable rehearsal

The newest 25 official 2026 House PTRs produced:

- 25 exact raw PDFs;
- 137 normalized events;
- 134 disclosed ranges and one disclosed exact amount;
- 28 transaction warnings where no ticker was disclosed;
- two image-only documents preserved as non-directional OCR warnings;
- one aggregate successful run, healthy source state and `quick_check=ok`.

The rehearsal used a disposable local v2 database. No production source,
schedule, AWS permission, report or email changed.

## Remaining release gates

1. Validate amendments, owner codes, open-ended amount ranges and a larger
   time-separated official sample before setting the fixture-agreement gate.
2. Decide whether image-only OCR is worth a separately bounded implementation;
   until then the warning PDF remains available for manual deep dive.
3. Measure raw-PDF database/archive growth before choosing production retention.
4. Implement Senate only after the acknowledgement/session design is approved.
5. Run a non-production history reconciliation against the contained legacy
   Congress rows; do not migrate midpoint values as ground truth.
6. Obtain a separate production source-release approval before scheduling.
