from emerald.shared_kernel.domain.models import Currency


class TestCurrencyAttributes:
    def test_usd_code(self) -> None:
        assert Currency.USD.code == "USD"

    def test_usd_symbol(self) -> None:
        assert Currency.USD.symbol == "$"

    def test_usd_name(self) -> None:
        assert Currency.USD.name == "US Dollar"

    def test_usd_decimal_places(self) -> None:
        assert Currency.USD.decimal_places == 2

    def test_jpy_decimal_places(self) -> None:
        assert Currency.JPY.decimal_places == 0

    def test_jpy_code(self) -> None:
        assert Currency.JPY.code == "JPY"

    def test_all_ten_currencies_exist(self) -> None:
        expected = {"USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "MXN", "BRL", "CNY"}
        actual = {c.code for c in Currency}
        assert actual == expected

    def test_eur_attributes(self) -> None:
        assert Currency.EUR.code == "EUR"
        assert Currency.EUR.symbol == "\u20ac"
        assert Currency.EUR.name == "Euro"
        assert Currency.EUR.decimal_places == 2

    def test_gbp_attributes(self) -> None:
        assert Currency.GBP.code == "GBP"
        assert Currency.GBP.symbol == "\u00a3"

    def test_mxn_attributes(self) -> None:
        assert Currency.MXN.code == "MXN"
        assert Currency.MXN.symbol == "MX$"
        assert Currency.MXN.name == "Mexican Peso"


class TestCurrencyEquality:
    def test_same_currency_is_equal(self) -> None:
        assert Currency.USD == Currency.USD

    def test_different_currencies_not_equal(self) -> None:
        assert Currency.USD != Currency.EUR


class TestCurrencyHashable:
    def test_usable_in_set(self) -> None:
        s = {Currency.USD, Currency.EUR, Currency.USD}
        assert len(s) == 2

    def test_usable_as_dict_key(self) -> None:
        d = {Currency.USD: "dollar", Currency.EUR: "euro"}
        assert d[Currency.USD] == "dollar"
