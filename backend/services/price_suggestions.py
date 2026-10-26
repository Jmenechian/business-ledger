"""Read-only matching over one customer's eligible historical references."""

import math
import re
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from fractions import Fraction

from backend.models.movement import Movement
from backend.models.price_suggestion import PriceReference, PriceSuggestion
from backend.services.errors import LedgerError
from backend.services.money import rounded

MIN_SIMILARITY = 0.65
MAX_PRODUCTS = 5
MAX_REFERENCES = 3


def normalize(value: str) -> str:
    text = "".join(
        char
        for char in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(char)
    )
    return " ".join(re.findall(r"[^\W_]+", text, re.UNICODE))


def similarity(query: str, candidate: str) -> float:
    if not candidate:
        return 0
    # Model, size and other numeric distinctions cannot be fuzzy substitutions.
    numbers = set(re.findall(r"\d+", query))
    if numbers and numbers != set(re.findall(r"\d+", candidate)):
        return 0
    query_tokens, candidate_tokens = query.split(), candidate.split()
    ordered = SequenceMatcher(None, query, candidate, autojunk=False).ratio()
    unordered = SequenceMatcher(
        None, " ".join(sorted(query_tokens)), " ".join(sorted(candidate_tokens)), autojunk=False
    ).ratio()
    remaining = candidate_tokens.copy()
    for token in sorted(query_tokens, key=len, reverse=True):
        match = next((item for item in remaining if item.startswith(token)), None)
        if match is None:
            break
        remaining.remove(match)
    else:
        return max(ordered, unordered, 0.85)
    return max(ordered, unordered)


def reliable_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None
    except (ValueError, OverflowError):
        return None


def reference(movement: Movement) -> PriceReference | None:
    if (
        movement.tipo == "payment"
        or not movement.cant
        or movement.cant <= 0
        or not math.isfinite(movement.debe)
        or movement.debe <= 0
    ):
        return None
    derived = movement.precio_unitario is None
    original = movement.precio_unitario
    if original is not None and (not math.isfinite(original) or original <= 0):
        return None
    try:
        price = rounded(
            Fraction(str(movement.debe)) / movement.cant if derived else Fraction(str(original))
        )
    except (ValueError, OverflowError, LedgerError):
        return None
    if price <= 0:
        return None
    return PriceReference(
        movement_id=movement.id,
        detalle=movement.detalle,
        precio_original=original,
        precio_unitario=price,
        precio_derivado=derived,
        fecha=movement.fecha,
        added_date=movement.added_date if reliable_time(movement.added_date) else None,
    )


def reference_order(item: PriceReference) -> tuple[datetime, int]:
    # ID is accounting order for ties/unknown dates, never a fabricated timestamp.
    return reliable_time(item.added_date) or datetime.min.replace(
        tzinfo=timezone.utc
    ), item.movement_id


def suggest(history: list[Movement], query: str) -> list[PriceSuggestion]:
    query = normalize(query)
    if len(query.replace(" ", "")) < 3:
        return []
    groups: dict[str, tuple[float, list[PriceReference]]] = {}
    scores: dict[str, float] = {}
    for movement in history:
        candidate = normalize(movement.detalle)
        if candidate not in scores:
            scores[candidate] = similarity(query, candidate)
        score = scores[candidate]
        if score < MIN_SIMILARITY:
            continue
        item = reference(movement)
        if item is None:
            continue
        key = " ".join(sorted(candidate.split()))
        previous_score, references = groups.setdefault(key, (score, []))
        references.append(item)
        groups[key] = max(score, previous_score), references
    products = []
    for key, (score, references) in groups.items():
        references.sort(key=reference_order, reverse=True)
        products.append((key, score, references[:MAX_REFERENCES]))
    # Stable tertiary name ordering is preserved by Python's stable sort.
    products.sort(key=lambda item: item[0])
    products.sort(key=lambda item: (item[1], reference_order(item[2][0])[0]), reverse=True)
    return [
        PriceSuggestion(
            detalle=references[0].detalle,
            similitud=round(score, 6),
            referencias=references,
        )
        for _, score, references in products[:MAX_PRODUCTS]
    ]
