# Hong Kong Float-Squeeze Source Coverage Assessment

Status: Local research complete; production release `NO_GO`

Assessment date: 2026-07-29 HKT

## Business conclusion

The free official SFC high-concentration notices are excellent late-stage
liquidity warnings, but they do not serve SmartFlow's intended early-discovery
use case.

Across every SFC High Shareholding Concentration announcement from 2025-01-01
through 2026-06-30:

- 27/27 notices disclosed an exact residual percentage held by "other
  shareholders" at publication;
- 27/27 cases had an other-shareholder residual at or below 10%;
- 0/27 notices were public before the price had already risen 100% using the
  reference move stated by the SFC;
- the median other-shareholder residual was 8.03%;
- the median stated pre-notice rerating was 474%;
- the least-rerated case was already up 193.6%;
- the information-date-to-announcement lag had a 14-calendar-day median and a
  9-to-22-day range.

The SFC itself says these notices describe the structure at the relevant
information date and may not reflect the current position. The fixed universe
and every source notice are preserved in
`research/hk_float_coverage/sfc_high_concentration_20250101_20260630.csv`.

## Method

The universe was fixed before measuring results:

- population: every item on the official SFC High Shareholding Concentration
  archive;
- announcement window: 2025-01-01 through 2026-06-30 inclusive;
- sample size: 27, with no hand-selected winners or exclusions;
- timing: `information_date` and `announcement_date` are stored separately;
- residual: issued shares in the notice's stated share-class scope minus the
  notice's identified concentrated holdings;
- rerating: the price increase and reference period stated in each SFC notice.

The reported other-shareholder residual is an upper-bound proxy for tradable
float, not proof that every residual share is freely tradable. Actual tradable
float may be lower. The SFC reference periods are not uniform. The rerating
figures therefore prove
that every notice was late relative to a large move, but must not be treated as
a comparable 60-day return series or a performance backtest.

One case, 02418, reports only the listed H-share denominator. Its 1.10% float is
not mixed with the issuer's domestic shares.

## Source-route finding

### SFC high-concentration notices

Permitted role: exact post-enquiry other-shareholder residual as an upper bound
for tradable float, plus liquidity-risk context.

Not permitted: early accumulation evidence, beneficial-owner transaction
direction, or a buy trigger.

Decision: retain `OVERHEATED` and late-risk use only.

### HKEX Disclosure of Interests and issuer records

HKEX's Terms of Use, last updated 19 August 2025, prohibit programmatic or
scripted access, systematic retrieval, derivative databases, web scraping and
text/data mining without express written permission. This applies beyond CCASS
and blocks an automated DI coverage test.

The audit therefore records `BLOCKED_BY_TERMS`; it does not misreport the
unmeasured coverage as 0%. SmartFlow must not build a DI daily-summary scraper
or automate issuer-document retrieval from HKEX under the current authority.

Permitted next routes:

1. obtain express written HKEX permission for the defined personal-research
   workflow; or
2. acquire a vendor licence that explicitly covers API/data-feed ingestion,
   local derived analytics and the intended retention period.

## Licensed-feed shortlist

| Route | Relevant documented capability | Main validation risk |
|---|---|---|
| FactSet Ownership API/DataFeed | Global security holders, shares held, percentage outstanding, stakeholder data, float and historical ownership | Confirm Hong Kong substantial-holder event latency and licence rights |
| LSEG Ownership V2 / Asia ownership | Global declarable stakes and as-reported holdings; Asia coverage; current and historical delivery | Confirm small-cap HK coverage, timestamps and share-class denominators |
| S&P Global Ownership | Institutional, fund, insider/individual ownership, public float and major-holder transactions via API/feed products | Confirm point-in-time availability and beneficial-holder treatment |
| Direct HKEX written permission | Primary DI and issuer evidence | Approval, permitted automation scope, storage and derived-work rights are unknown |

Public product descriptions do not publish a comparable all-in price. No vendor
should be purchased from marketing coverage alone.

## Trial acceptance gate

A vendor trial should use this untouched 27-case event set plus 27
market-cap/liquidity-matched non-event controls. SmartFlow should not tune its
current score during the trial.

Minimum requirements:

- at least 90% security and share-class mapping across both event and control
  sets;
- issued shares and vendor free float must be point-in-time reproducible, with
  `as_of` and first `available_at` timestamps;
- at least two comparable major-holder share-count observations before the SFC
  information date in at least 70% of event cases;
- an early evidence package must be available before the stock first doubles
  from the pre-move baseline in at least 50% of event cases;
- 100% correct H-share, domestic-share and dual-listing denominator handling;
- corrections and restatements must be versioned rather than silently replacing
  prior evidence;
- the licence must permit personal automated research, local retention and
  derived scores without redistribution;
- false-positive rate and lead time must be measured on controls before any
  production/email proposal.

If no candidate passes, the economically correct decision is to retain
SmartFlow as descriptive and late-risk intelligence rather than pay for a feed
that still arrives after the move.

## Recommendation

Do not deploy the early float-squeeze signal with current free sources.

Request a time-limited FactSet Ownership trial first because its documented API
exposes security holders, share counts, percentage outstanding and float in one
contract. Use LSEG as the second benchmark and S&P as the third. Evaluate them
against the acceptance gate before discussing subscription cost.

## Primary sources

- SFC archive:
  https://www.sfc.hk/en/News-and-announcements/High-shareholding-concentration-announcements
- HKEX Terms of Use:
  https://www.hkex.com.hk/global/exchange/terms-of-use?sc_lang=en
- HKEX DI search description:
  https://di.hkex.com.hk/di/NSSrchMethod.aspx
- FactSet Ownership API:
  https://developer.factset.com/api-catalog/factset-ownership-api
- LSEG Ownership data:
  https://www.lseg.com/en/data-analytics/financial-data/company-data/company-ownership-information-profiles
- S&P Global Ownership dataset:
  https://www.marketplace.spglobal.com/en/datasets/ownership-%2820%29
