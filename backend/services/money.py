from decimal import Decimal
from fractions import Fraction

from backend.services.errors import LedgerError

MAX_AMOUNT = 9007199254740991


def rounded(value: Fraction) -> int:
    sign = -1 if value < 0 else 1
    numerator = abs(value.numerator)
    integer, remainder = divmod(numerator, value.denominator)
    result = sign * (integer + (2 * remainder >= value.denominator))
    if abs(result) > MAX_AMOUNT:
        raise LedgerError("el saldo supera el límite permitido")
    return result


def positive_amount(value: Decimal) -> int:
    # Bound before converting to Fraction, including enormous exponents.
    if (
        not value.is_finite()
        or value < Decimal("0.5")
        or value >= Decimal(MAX_AMOUNT) + Decimal("0.5")
    ):
        raise LedgerError("el importe está fuera del rango permitido")
    return rounded(Fraction(value))


def next_balance(previous: int | float, debit: int, credit: int) -> int:
    return rounded(Fraction(str(previous)) + debit - credit)
