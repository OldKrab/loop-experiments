from payments.invoice import Line, invoice_total


def test_single_currency_invoice():
    lines = [Line("Seat", 1_000, "USD", quantity=3), Line("Support", 500, "USD")]
    assert invoice_total(lines, "USD") == 3_500


def test_jpy_invoice_from_usd_prices():
    lines = [Line("Seat", 1_000, "USD", quantity=2)]
    assert invoice_total(lines, "JPY") == 2_990
