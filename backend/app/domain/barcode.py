"""Barcode normalisation and validation (EAN-8, EAN-13, UPC-A)."""
from __future__ import annotations

import re


class InvalidBarcode(ValueError):
    pass


def _check_digit_ok(digits: str) -> bool:
    body, check = digits[:-1], int(digits[-1])
    # GS1: weights alternate 3,1 starting from the digit adjacent to the check digit.
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return (10 - total % 10) % 10 == check


def compute_check_digit(body: str) -> str:
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return str((10 - total % 10) % 10)


def normalize_barcode(raw: str) -> str:
    """Return canonical form: EAN-8 stays 8 digits; UPC-A (12) is zero-padded to EAN-13."""
    if raw is None:
        raise InvalidBarcode("empty barcode")
    cleaned = re.sub(r"[\s-]", "", raw)
    if not cleaned.isdigit():
        raise InvalidBarcode("barcode must contain digits only")
    if len(cleaned) == 12:
        cleaned = "0" + cleaned
    if len(cleaned) not in (8, 13):
        raise InvalidBarcode("unsupported barcode length (expected EAN-8, UPC-A or EAN-13)")
    if not _check_digit_ok(cleaned):
        raise InvalidBarcode("barcode check digit is invalid")
    return cleaned
