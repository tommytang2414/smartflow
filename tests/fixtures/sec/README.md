# SEC parser fixtures

These minimized XML fixtures preserve the relevant structure and values from official SEC EDGAR filings. They are stored locally so parser behavior is deterministic and does not depend on SEC network availability.

- `form4_non_market_official_excerpt.xml`: minimized from accession `0001140361-26-018962`, including transaction codes `A` and `J` that must not be classified as open-market sales. Source: https://www.sec.gov/Archives/edgar/data/2002660/000114036126018962/form4.xml
- `form144_official_excerpt.xml`: minimized from accession `0001921094-25-001148`, a Form 144 notice for Meta Platforms. Source: https://www.sec.gov/Archives/edgar/data/1326801/000192109425001148/primary_doc.xml

Synthetic P/S/G cases in `tests/test_sec_parsers.py` use the same SEC ownership XML schema to exercise transaction-code boundaries that are not present in the two captured filings.
