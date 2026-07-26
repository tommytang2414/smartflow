# Congress Disclosure Business and Technical Assessment

Date: 2026-07-26 HKT

Status: House shadow v3 is deployed but degraded on raw-only DocID `20033725`.
The v4 cross-page remediation is locally verified and pending its exact
production gate. Senate remains pending.

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
- parser version: `congress-house-ptr-v4` for new evidence after deployment;
  v2/v3 remain accepted historical production evidence
- an observed share-price suffix is preserved as `amount_note` and never changes
  the disclosed bounds or null `value`
- a cross-page row stops amount collection once its strict disclosed range is
  complete; continued asset text and ticker are preserved, while official
  `D:` disclosure text is stored separately as `transaction_note`

Positively identified amendments are not treated as another directional report.
The exact PDF is retained and the document becomes a non-directional
`amendment_requires_reconciliation` warning until the original report can be
linked and row-level replacement/addition semantics are defined.

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
- A completed DocID is a cache hit only when it has raw evidence and at least one
  normalized child. Routine polls do not redownload completed PDFs, while a
  raw-only parser failure remains retryable.
- The newest-unseen backlog advances in bounded batches of 25 with a 50 MiB
  aggregate PDF cap and a 300-second child-process timeout.
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

## Time-separated and amendment validation

A 50-report sample spaced across the complete current House index from
1 January through 22 July 2026 produced:

- 47 parsed text-layer reports and three explicit OCR warnings;
- 556 events: 289 purchases, 258 sales, six exchanges and three
  non-directional document notices;
- 110 missing-ticker warnings and one valid open-ended
  `Spouse/DC Over $1,000,000` range;
- zero parser errors after correcting narrow date columns and cross-page amount
  continuations.

An official 2020 text-layer amendment was independently recognized from its
explicit amendment statement and normalized only as a non-directional
reconciliation warning. Official image-only amendments remain covered by the
existing OCR warning boundary.

## Raw-storage measurement

For the same newest-25 sample:

- exact PDF bytes: 1,683,635;
- base64 payload bytes: 2,244,872 (33.33% encoding overhead);
- complete SQLite v2 database: 2,519,040 bytes;
- average official PDF: approximately 67 KB.

A linear estimate for the current 313-report index is approximately 31.5 MB of
SQLite storage. This is operationally modest, but it is an estimate rather than
a retention guarantee. Production review must account for S3 object versioning,
monthly archives and multi-year history before enabling backfill.

## Legacy reconciliation

The contained local legacy database has 1,499 Congress rows from 25 April 2025
through 18 May 2026:

- 752 BUY, 742 SELL and five EXCHANGE labels;
- 263 explicitly tagged `quiverquant` and 1,236 from an unspecified legacy API;
- 1,236 range disclosures stored as the lower bound rather than the disclosed
  range;
- all 1,499 use legacy identities without official report-plus-row traceability;
- zero rows can be linked to an immutable official House/Senate report ID and row.

These rows remain audit history only. Do not train, validate, backfill or report
them as corrected Congress ground truth.

## Prepared production design

`CONGRESS_HOUSE_SHADOW_RELEASE_RUNBOOK.md` defines:

- a separate `congress-house-v2-shadow.db`, because adding a Congress health row
  to the SEC database would deliberately fail the SEC-only publisher;
- an hourly collector, daily read-only audit and daily recoverable snapshot;
- a dedicated hash-locked PDF runtime that does not modify shared Python;
- an exact write-only S3 current key and monthly audit archive;
- 30-day non-current retention for the current key, no expiry for monthly audit
  snapshots, a 512 MiB publisher cap and measured cost estimate;
- zero Lambda, email, MiniMax, EventBridge, legacy DB or SEC DB change; and
- a recoverable rollback that never deletes evidence.

## Remaining release gates

1. Obtain approval of the exact v4 release commit and bounded parser-deployment
   manifest. Do not manually reprocess DocID `20033725`.
2. Let the next daemon-fired run process the raw-only report, then start a new
   14-day/99% House observation window from that scheduled success.
3. Pass the production audit and new House observation
   window before proposing any email integration.
4. Decide whether image-only OCR is worth a separately bounded implementation;
   until then the exact warning PDF remains available for manual deep dive.
5. Define original-to-amendment row reconciliation before amendments can enter
   directional ranking.
6. Implement Senate only after the acknowledgement/session design is approved.
