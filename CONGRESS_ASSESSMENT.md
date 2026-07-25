# Congress Disclosure Business and Technical Assessment

Date: 2026-07-26 HKT

Status: House offline parser/normalizer complete; live ingestion and Senate adapter pending

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
fails closed on missing rows, dates, amount ranges or identity fields. It
extracts a ticker only when the report discloses one; it does not infer a ticker
from an asset name.

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
- parser version: `congress-house-ptr-v1`

## Remaining release gates

1. Add bounded House HTTP acquisition with size, redirect, host and content checks.
2. Preserve exact PDF bytes as immutable raw evidence outside the M3 fact pack.
3. Add aggregate collector outcomes, source health and idempotent v2 persistence.
4. Validate more official PDF layouts, amendments, owner codes and open-ended
   amount ranges before setting the fixture-agreement gate.
5. Implement Senate only after the acknowledgement/session design is approved.
6. Run a non-production history reconciliation against the contained legacy
   Congress rows; do not migrate midpoint values as ground truth.
7. Obtain a separate production source-release approval before scheduling.
