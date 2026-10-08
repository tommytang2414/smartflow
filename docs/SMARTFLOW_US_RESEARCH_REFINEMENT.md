# US research refinement — 2026-10-08

SmartFlow remains stock-first US/HK smart-money research. This owner-approved
change improves the isolated manual Mac report; it does not activate trading,
production collectors, delivery or an unattended schedule.

## What the report adds

- A compact five-stock opening, followed by each falsifiable thesis, supporting
  originals, counterevidence, invalidation condition and next evidence.
- Form 4 reporting-owner roles/titles, field-linked footnotes, disclosed holdings
  after the transaction, ownership kind and filing-level plan indicator.
- SEC company current/periodic reports selected from official submissions metadata.
  Quotes are exact bounded extracted-text spans, never model-generated summaries.
- Content-based comparison with the verified previous packet. Issuer/accession
  and raw/text hashes distinguish changed originals; fresh retrieval/receipt IDs
  do not make the same original new. Source window metadata is explicit.
- Comparison with approved previous research. A new document is new research
  context; it is not a new trade and cannot establish an earlier trader's motive.
- Explicit failure taxonomy and unavailable price/volume/return status.

Form 4 context does not change the upstream normalized contract. IDs use the
production parser's accepted order across derivatives and non-derivatives;
skipped raw nodes cannot shift the join. Issuer, date, code, title, quantity,
price and acquired/disposed signature must agree or context stays unknown.
Derived context v2 explicitly flags weighted-average purchase/sale wording that
conflicts with the disclosed P/S code. It preserves the code and unresolved note.
Footnote fields render in sorted order so serialized JSON can reproduce report bytes.
Joint reporting owners are filing-level, not separate execution attribution.
Repeat activity counts distinct filings, not repeated lines. Holdings-after is
not current total beneficial ownership. The plan checkbox is not proof that
all rows use a plan; false/missing is not proof of discretion.

P/S represents open-market **or private** purchase/sale, per the
[SEC ownership codes](https://www.sec.gov/edgar/searchedgar/ownershipformcodes.html).
Never automatically label all such rows open-market conviction.

## SEC snapshot audit

Read-only input: snapshot generated 2026-10-07T23:55:06Z, SHA-256
`f9879ae8912aff7c1471a13b70c99aa94b7bb0cf5c9b1e8a3bb96b8c55a71b46`.
The following 14-day counts are snapshot-relative, not live collector health.

| Collector | Successful | Source errors | Parser errors | Success rate |
|---|---:|---:|---:|---:|
| Form 4 | 3,834 | 101 | 98 | 95.07% |
| Form 144 | 326 | 10 | 0 | 97.02% |

Source failures record only `SECSourceError / SEC request failed`; their original
transport exceptions were not retained. No inference of HTTP 403/429, timeout or
DNS failure is justified from these records. The 98 parser failures involve 47
distinct accessions; 16 repeatedly rejected accessions account for 51 failures.

All 106 historical raw-only Form 4 filings are parseable XML with no transaction
nodes. Of these, 73 have a Section 16 administrative flag without remarks or
holdings, and 33 have holdings-only content (31 with footnotes). The current
parser contract rejects both shapes. Raw-only filings are retried, and a parser
exception aborts the batch. This is a transactionless contract gap, not corrupt
XML. Upstream repair requires dedicated administrative/holdings contracts and
fixtures; never create fake trades or rewrite historic failure records. This
release only exposes the evidence and preserves the 99% gate.

## Company data contract

[SEC API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
explicitly permits keyless public API use. Existing issuer aliases supply the CIK;
no ticker-only identity guess. Read `data.sec.gov/submissions/CIK##########.json`,
then at most the latest recent current report and periodic report per alias.
No bulk market scrape, new auth or copied credentials. A public contact User-Agent,
serial requests spaced at least 0.55 seconds, bounded downloads and immediate
stop on 403/429 follow
[SEC fair access](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data).

The first bundle holds fourteen primary reports for seven approved aliases;
eight reports belong to the four identity-resolved dossiers selected in this run.
GOOGL stays unresolved because the supplied insider stock-class proof is Class C,
which cannot automatically be assigned to the GOOGL Class A listing.

Raw bytes, extracted text, submissions JSON and alias hash are retained and
verified. Loading checks exact metadata against submissions, source path against
primaryDocument, exact quotes against the raw-derived text, and each document's
first-observed timestamp against cutoff. The immutable run manifest seals every
original. `acceptanceDateTime` is SEC acceptance, not proven first dissemination;
`reportDate` is not public availability. First observed is the conservative anchor.

Company reports are bounded current context. Primary 8-K announcements may point
to an exhibit not imported here; do not invent its earnings or guidance content.
Items 2.02/7.01 may be furnished rather than filed, per the
[official Form 8-K](https://www.sec.gov/files/form8-k.pdf).
No earnings calendar, macro, transcript or full-news coverage is claimed.

## Price source research

No installed approved key-based feed was found. Existing Yahoo helpers use an
unofficial endpoint. Stooq official terms/download/adjustment information could
not be verified from readable primary evidence. Neither route is enabled.
Prices, volume, post-disclosure returns and paper outcomes remain unavailable;
no substitution of insider trade prices or disclosure-range midpoints.

A later licensed feed/import must document listing identity, currency/timezone,
complete session dates, split/dividend/volume adjustment semantics, corporate
action coverage, raw hashes and rights for storage/private reporting/GPT processing.
Public-availability anchors and benchmarks are required before outcome claims.
This report makes no validated alpha claim.

## Operation and verification

```powershell
py -3 -m smartflow.research fetch-context --aliases data/research-prototype/aliases.json `
  --destination data/research-prototype/us-context-YYYYMMDD `
  --contact YOUR_PUBLIC_CONTACT_EMAIL
```

Use a new destination; don't overwrite a sealed bundle. Transfer exact files by
the existing pinned SCP route. On Mac, add `--company-context us-context` to the
runbook's manual `prepare`/`analyze` commands. Keep all prior reports and state.

```powershell
py -3 -X utf8 -m ops.verify_research_prototype
py -3 -X utf8 -m unittest discover -s tests
py -3 -m compileall -q smartflow/research ops/verify_research_prototype.py
```

The disposable rehearsal covers skipped/derivative transaction ordering,
signature mismatch, missing plan indicator, raw footnotes/holdings, hidden HTML,
company metadata/quote/hash tamper, future cutoff, unknown thesis citations and
unverified prices, alongside the existing import/review/history controls.
The independent code review additionally required explicit no-causality and
filing-level owner wording; both are applied. Actual report acceptance and release
hashes are recorded in the runbook and handoff after the Mac run.
