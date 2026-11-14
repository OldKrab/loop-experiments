---
name: payments-domain
description: Rules of the payments codebase - money representation, minor units, currency conversion, rounding, invoices, and refunds. Use when reading or changing code under payments/.
---
# Payments domain rules

## Money representation
- Amounts are always `int` in the currency's **minor unit**: cents for USD, yen for JPY, fils for KWD.
- Never use `float` for money. Use `decimal.Decimal` for intermediate values.

## Minor units (ISO 4217 exponent)
Currencies have different numbers of decimal places:

| Currency | Exponent | 1 major unit = |
|---|---|---|
| USD, EUR, GBP | 2 | 100 minor |
| JPY | 0 | 1 minor |
| KWD | 3 | 1000 minor |

The exponents live in `payments.currency.MINOR_UNITS`. Any conversion between major and minor units must use `10 ** MINOR_UNITS[currency]`. Hard-coding `100` is the most common bug in this codebase: it is right for USD and wrong for JPY and KWD.

## Conversion
- `RATES` gives units of each currency per 1 USD. Convert src -> USD -> dst in major units, then to minor units of dst.
- Round only once, at the end, to the destination's minor unit.

## Rounding
- Banker's rounding (`ROUND_HALF_EVEN`) everywhere. Finance reconciles against a ledger that uses it.

## Invoices and refunds
- An invoice total is the sum of lines converted individually into the billing currency.
- Refunds can never exceed the amount paid minus what was already refunded.

## Tests
- `tests/test_currency.py` covers conversion and formatting for every currency in `RATES`. When adding a currency, add a round-trip test for it.
