# HKEX CCASS Business, Data, and Technical Assessment

Date: 2026-07-23 HKT

Status: offline contract complete; production collection blocked by access terms

## Business meaning

CCASS reports balances held in participant accounts after settlement for a specified security and date. A participant may be a broker, bank, custodian, clearing agency, or investor participant. HKSCC treats depositing participants as principals for CCASS operation but does not recognise or disclose the interests of their underlying clients.

Therefore a participant balance is not:

- the participant's beneficial ownership;
- proof of a purchase or sale by that participant;
- a unique investor position;
- director dealing or substantial-shareholder disclosure; or
- sufficient evidence of accumulation, distribution, retail activity, or “smart money”.

## Legacy semantic defects

The contained collector currently makes unsupported transformations:

| Legacy rule | Defect | v2 treatment |
|---|---|---|
| `BrkT5 >= 69% -> SELL/RED` | Custodian concentration does not prove bearish action or drawdown | Descriptive top-5 participant concentration only |
| `BrkT5 increase >= 5% -> BUY` | Balance changes can arise from transfers, deposits, withdrawals, settlement, or client activity | Non-directional custody balance change |
| `FUTU >= 10% -> SELL` | Participant account balance does not identify retail beneficial owners or prove a contra-indicator | No directional event |
| Exclude `A00005` to create “adjusted float” | Sum of selected CCASS balances is not issuer free float | No adjusted-float claim |
| Broker-only top five labelled “莊家” | Participant classification is not beneficial-owner identity | No controller/market-manipulation claim |

## Legacy evidence audit

| Database | Holdings | Metrics | Date range | Directional signals | Supported |
|---|---:|---:|---|---:|---:|
| Local legacy DB | 133,955 | 659 | 2026-03-23 to 2026-05-22 | 352 SELL | 0 |
| Immutable production snapshot | 316,811 | 1,555 | 2026-03-23 to 2026-07-20 | 849 SELL, 1 BUY | 0 |

The raw legacy holdings remain audit evidence. Existing directional signals and RED/AMBER/GREEN labels must not enter trusted reports or training/validation datasets as ground truth.

## V2 functional contract

For an approved structured snapshot, v2 creates:

1. one `ccass_participant_holding_snapshot` per participant;
2. one `ccass_participant_concentration_snapshot` per stock/date;
3. immutable raw evidence linked to every normalized event;
4. exact share quantities and source-reported percentage of issued shares;
5. transparent top-1, top-5, participant-count, total-CCASS-shares, and HHI attributes; and
6. explicit text that concentration is participant-account concentration, not beneficial ownership.

No event receives a `BUY` or `SELL` side.

## Access and compliance gate

The HKEX public CCASS search terms state that the information is for personal and non-commercial use and prohibit, without express written permission, scripted/mechanical access and systematic creation of collections, databases, directories, or derivative works.

Consequences:

- keep `smartflow/collectors/hkex_ccass.py` disabled;
- do not run live automated fixture capture or historical backfill;
- do not copy HKEX holdings into the test repository;
- use synthetic fixtures until an authorised route exists; and
- require written permission/licence or an authorised provider before production release.

## Technical acceptance gates

- structured parser rejects duplicate participants, invalid IDs, fractional/negative shares, and invalid percentages;
- normalized side is always null;
- concentration calculations expose their exact inputs and interpretation limit;
- reconciliation never converts disappearance/appearance into sale/purchase;
- malformed snapshots preserve raw evidence and record parser failure;
- ingestion reruns are idempotent; and
- production collector/scheduler remain disabled.
