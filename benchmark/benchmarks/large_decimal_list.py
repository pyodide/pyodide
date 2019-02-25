# setup: from decimal import Decimal ; A = [Decimal('2.1') for i in range(1000)] ; B = [Decimal('3.2') for i in range(1000)]  # noqa
# run: large_decimal_list(A, B)


def large_decimal_list(A, B):
    return [a * b for a, b in zip(A, B)]
