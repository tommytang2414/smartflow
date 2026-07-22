# SEC parser fixtures

These minimized XML fixtures preserve the relevant structure and values from official SEC EDGAR filings. They are stored locally so parser behavior is deterministic and does not depend on SEC network availability.

- `form4_non_market_official_excerpt.xml`: minimized from accession `0001140361-26-018962`, including transaction codes `A` and `J` that must not be classified as open-market sales. Source: https://www.sec.gov/Archives/edgar/data/2002660/000114036126018962/form4.xml
- `form4_purchase_official_excerpt.xml`: minimized from accession `0001193125-26-089784`, an actual Shift4 `P` transaction. Source: https://www.sec.gov/Archives/edgar/data/1805608/000119312526089784/ownership.xml
- `form4_sale_official_excerpt.xml`: minimized from accession `0000021344-26-000137`, an actual Coca-Cola `S` transaction. Source: https://www.sec.gov/Archives/edgar/data/21344/000002134426000137/form4.xml
- `form144_official_excerpt.xml`: minimized from accession `0001921094-25-001148`, a Form 144 notice for Meta Platforms. Source: https://www.sec.gov/Archives/edgar/data/1326801/000192109425001148/primary_doc.xml
- `form4_derivative_official_excerpt.xml`: minimized from accession `0001628280-26-049165`, a derivative-only Form 4 for Erie Indemnity. Source: https://www.sec.gov/Archives/edgar/data/922621/000162828026049165/wk-form4_1784747789.xml

`expectations.json` is the machine-readable agreement contract. Run `python ops/verify_sec_fixtures.py`; the Phase 1 gate requires at least 95% of maintained official fixtures to pass every declared expectation.

Synthetic P/S/G cases in `tests/test_sec_parsers.py` use the same SEC ownership XML schema to exercise transaction-code boundaries that are not present in the two captured filings.
