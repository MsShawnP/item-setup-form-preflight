"""Fuzzy column matching engine.

Maps uploaded file headers to schema fields using a layered approach:
exact match after normalization, alias substring containment, then
difflib fuzzy matching. Every uploaded header and every schema field
appears in the result -- nothing is silently dropped.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from enum import StrEnum

from src.engine.models import SchemaConfig


class MatchStatus(StrEnum):
    MATCHED = "matched"
    AMBIGUOUS = "ambiguous"
    UNMATCHED = "unmatched"


@dataclass
class ColumnMatch:
    """A single schema-field-to-uploaded-header mapping."""

    schema_field: str
    uploaded_header: str | None
    confidence: float  # 0.0 to 1.0
    status: MatchStatus
    candidates: list[str] = field(default_factory=list)


@dataclass
class MatchResult:
    """Full result of matching uploaded headers to a schema."""

    matches: list[ColumnMatch]
    unmatched_headers: list[str]  # uploaded headers not matched to any field
    unmatched_fields: list[str]  # schema fields with no match


# ---------------------------------------------------------------------------
# Alias map
# ---------------------------------------------------------------------------

# Keys are normalized schema field names. Values are lists of known
# aliases that a user's spreadsheet might use. Keep lowercase, no
# leading/trailing whitespace. The schema field name itself is always
# implicitly included.

_WALMART_ALIASES: dict[str, list[str]] = {
    "upc": [
        "upc", "upc-a", "upc_a", "upc a", "upc number", "upc code",
        "gtin", "gtin12", "gtin-12", "gtin 12", "barcode",
    ],
    "case_gross_weight_lb": [
        "gross weight", "gross wt", "case weight", "weight",
        "case gross weight", "case gross weight lb",
    ],
    "case_length_in": [
        "length", "case length", "item length", "l in",
        "case length in",
    ],
    "case_width_in": [
        "width", "case width", "item width", "w in",
        "item width in", "case width in",
    ],
    "case_height_in": [
        "height", "case height", "item height", "h in",
        "case height in",
    ],
    "case_pack_qty": [
        "case pack", "pack qty", "pack quantity", "case count",
        "qty per case", "cs pk", "case pack qty",
    ],
    "product_name": [
        "product name", "item name", "product", "name",
        "description", "item description",
    ],
    "brand": [
        "brand", "brand name", "manufacturer",
    ],
    "category": [
        "category", "department", "class", "segment",
    ],
    "country_of_origin": [
        "country of origin", "coo", "country", "origin",
    ],
    "serving_size": [
        "serving size", "srv size", "portion",
    ],
    "calories": [
        "calories", "kcal", "cal",
    ],
    "storage_type": [
        "storage type", "storage", "temp class", "temp zone",
    ],
    "product_description": [
        "product description", "long description", "item desc",
        "item description",
    ],
    "total_fat_g": [
        "total fat", "total fat g", "fat g", "fat",
    ],
    "sodium_mg": [
        "sodium", "sodium mg", "na mg", "salt",
    ],
}

_COSTCO_ALIASES: dict[str, list[str]] = {
    "upc": [
        "upc", "gtin", "gtin14", "gtin-14", "gtin 14", "itf-14",
        "itf14", "itf 14", "case gtin", "case barcode", "barcode",
    ],
    "case_pack_qty": [
        "club pack qty", "club pack quantity", "pack qty",
        "pack quantity", "case count", "case pack qty",
    ],
    "inner_pack_count": [
        "inner pack count", "inner pack", "inner pack qty",
        "inner count", "inners per case",
    ],
    "club_pack_length_in": [
        "club pack length", "club pack length in", "club length",
        "club pack l",
    ],
    "club_pack_width_in": [
        "club pack width", "club pack width in", "club width",
        "club pack w",
    ],
    "club_pack_height_in": [
        "club pack height", "club pack height in", "club height",
        "club pack h",
    ],
    "shelf_life_days": [
        "shelf life", "shelf life days", "best by days",
        "days of shelf life",
    ],
    "club_membership_tier": [
        "club membership tier", "membership tier", "member tier",
        "membership level",
    ],
    "executive_member_price": [
        "executive member price", "executive price",
        "exec member price",
    ],
    "executive_discount_pct": [
        "executive discount pct", "executive discount",
        "exec discount", "executive discount percent",
    ],
}

_UNFI_ALIASES: dict[str, list[str]] = {
    "upc": [
        "upc", "gtin", "gtin14", "gtin-14", "gtin 14", "itf-14",
        "itf14", "itf 14", "case gtin", "case barcode", "barcode",
    ],
    "wholesale_price": [
        "wholesale price", "wholesale", "whs price", "whsl",
        "wholesale cost",
    ],
    "list_price": [
        "list price", "list", "srp", "retail price",
        "suggested retail price",
    ],
    "map_price": [
        "map price", "map", "minimum advertised price",
        "min advertised price",
    ],
    "ti": [
        "ti", "cases per layer", "cases per tier",
        "case per layer", "tier count",
    ],
    "hi": [
        "hi", "layers per pallet", "layers", "pallet layers",
        "layer count", "high",
    ],
    "pallet_weight_lb": [
        "pallet weight", "pallet weight lb", "pallet wt",
        "plt weight", "full pallet weight",
    ],
    "shelf_life_days": [
        "shelf life", "shelf life days", "best by days",
        "days of shelf life",
    ],
    "has_promo_deal": [
        "has promo deal", "promo deal", "has promotion",
        "deal flag",
    ],
    "promo_start_date": [
        "promo start date", "promo start", "deal start",
        "promotion start",
    ],
    "promo_end_date": [
        "promo end date", "promo end", "deal end",
        "promotion end",
    ],
    "promo_price": [
        "promo price", "deal price", "promotional price",
        "promotion price",
    ],
}

_KEHE_ALIASES: dict[str, list[str]] = {
    "upc": [
        "upc", "gtin", "gtin14", "gtin-14", "gtin 14", "itf-14",
        "itf14", "itf 14", "case gtin", "case barcode", "barcode",
    ],
    "wholesale_price": [
        "wholesale price", "wholesale", "whs price", "whsl",
        "wholesale cost",
    ],
    "list_price": [
        "list price", "list", "srp", "retail price",
        "suggested retail price",
    ],
    "cases_per_layer": [
        "cases per layer", "ti", "cases per tier",
        "case per layer", "tier count",
    ],
    "layers_per_pallet": [
        "layers per pallet", "hi", "layers", "pallet layers",
        "layer count", "high",
    ],
    "pallet_weight_lb": [
        "pallet weight", "pallet weight lb", "pallet wt",
        "plt weight", "full pallet weight",
    ],
    "shelf_life_days": [
        "shelf life", "shelf life days", "best by days",
        "days of shelf life",
    ],
    "has_promo_deal": [
        "has promo deal", "promo deal", "has promotion",
        "deal flag",
    ],
    "promo_start_date": [
        "promo start date", "promo start", "deal start",
        "promotion start",
    ],
    "promo_end_date": [
        "promo end date", "promo end", "deal end",
        "promotion end",
    ],
    "promo_price": [
        "promo price", "deal price", "promotional price",
        "promotion price",
    ],
}

# Per-partner alias lookup
_PARTNER_ALIAS_MAPS: dict[str, dict[str, list[str]]] = {
    "walmart": _WALMART_ALIASES,
    "costco": _COSTCO_ALIASES,
    "unfi": _UNFI_ALIASES,
    "kehe": _KEHE_ALIASES,
}

# Unified alias map: merge all partner aliases. Used as fallback for
# fields not overridden by a specific partner, and by get_alias_map().
_ALIAS_MAP: dict[str, list[str]] = {}

for _partner_map in (_WALMART_ALIASES, _COSTCO_ALIASES, _UNFI_ALIASES, _KEHE_ALIASES):
    for _field, _aliases in _partner_map.items():
        if _field not in _ALIAS_MAP:
            _ALIAS_MAP[_field] = []
        _seen = set(_ALIAS_MAP[_field])
        for _a in _aliases:
            if _a not in _seen:
                _ALIAS_MAP[_field].append(_a)
                _seen.add(_a)


def _get_effective_aliases(partner: str, field_name: str) -> list[str]:
    """Get aliases for a field, preferring the partner's own map.

    If the partner defines aliases for this field, use those exclusively.
    Otherwise fall back to the merged global map (covers shared fields
    like product_name, brand, case dimensions that are defined once in
    the Walmart baseline).
    """
    partner_map = _PARTNER_ALIAS_MAPS.get(partner, {})
    if field_name in partner_map:
        return partner_map[field_name]
    return _ALIAS_MAP.get(field_name, [field_name])


def get_alias_map() -> dict[str, list[str]]:
    """Return a copy of the unified alias map across all partners.

    Includes Walmart, Costco, UNFI, and KeHE aliases merged together.
    """
    return {k: list(v) for k, v in _ALIAS_MAP.items()}


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Lowercase, strip, remove special chars except spaces, collapse spaces."""
    lowered = text.lower().strip()
    # Keep only alphanumeric and spaces
    cleaned = re.sub(r"[^a-z0-9 ]", " ", lowered)
    # Collapse multiple spaces
    return re.sub(r"\s+", " ", cleaned).strip()


# ---------------------------------------------------------------------------
# Matching engine
# ---------------------------------------------------------------------------

# Thresholds
_EXACT_CONFIDENCE = 1.0
_CONTAINMENT_CONFIDENCE_HIGH = 0.9
_CONTAINMENT_CONFIDENCE_LOW = 0.7
_FUZZY_THRESHOLD = 0.6


def match_columns(headers: list[str], schema: SchemaConfig) -> MatchResult:
    """Match uploaded file headers to schema fields.

    Algorithm layers (each schema field tries in order):
      1. Exact match after normalization -> confidence 1.0
      2. Alias containment (alias in header or header in alias) -> 0.7-0.9
      3. difflib fuzzy match above threshold -> ratio as confidence
      4. If multiple fuzzy candidates tie, mark AMBIGUOUS

    Each uploaded header can match at most one schema field. Each
    schema field can match at most one header. First-best-match wins.

    Args:
        headers: Column headers from the uploaded file.
        schema: Partner schema config with required_fields.

    Returns:
        MatchResult with every field and header accounted for.
    """
    # Build list of schema field names
    schema_fields = [f.name for f in schema.required_fields]

    # Normalize headers once
    norm_headers = [_normalize(h) for h in headers]

    # Track which headers and fields have been claimed
    claimed_headers: set[int] = set()  # indices into headers list
    matches: list[ColumnMatch] = []
    partner = schema.partner

    for field_name in schema_fields:
        match = _match_single_field(
            field_name, headers, norm_headers, claimed_headers, partner,
        )
        if match.uploaded_header is not None:
            # Find the index and claim it
            for idx, h in enumerate(headers):
                if h == match.uploaded_header and idx not in claimed_headers:
                    claimed_headers.add(idx)
                    break
        matches.append(match)

    # Collect unmatched headers (those not claimed by any field)
    unmatched_headers = [
        headers[i] for i in range(len(headers))
        if i not in claimed_headers
    ]

    # Collect unmatched fields
    unmatched_fields = [
        m.schema_field for m in matches
        if m.status == MatchStatus.UNMATCHED
    ]

    return MatchResult(
        matches=matches,
        unmatched_headers=unmatched_headers,
        unmatched_fields=unmatched_fields,
    )


def _match_single_field(
    field_name: str,
    headers: list[str],
    norm_headers: list[str],
    claimed: set[int],
    partner: str = "",
) -> ColumnMatch:
    """Try to match a single schema field to the best available header."""
    norm_field = _normalize(field_name)
    aliases = _get_effective_aliases(partner, field_name) if partner else _ALIAS_MAP.get(field_name, [field_name])

    # Always include the field name itself and its normalized form as aliases
    all_aliases = set(aliases)
    all_aliases.add(field_name)
    all_aliases.add(norm_field)
    # Normalize all aliases
    norm_aliases = {_normalize(a) for a in all_aliases}

    # --- Layer 1: Exact match ---
    for idx, norm_h in enumerate(norm_headers):
        if idx in claimed:
            continue
        if norm_h in norm_aliases:
            return ColumnMatch(
                schema_field=field_name,
                uploaded_header=headers[idx],
                confidence=_EXACT_CONFIDENCE,
                status=MatchStatus.MATCHED,
            )

    # --- Layer 2: Containment (alias in header or header in alias) ---
    best_containment: tuple[int, float] | None = None
    for idx, norm_h in enumerate(norm_headers):
        if idx in claimed:
            continue
        for alias in norm_aliases:
            if not alias or not norm_h:
                continue
            if alias in norm_h or norm_h in alias:
                # Longer overlap = higher confidence
                overlap = min(len(alias), len(norm_h)) / max(len(alias), len(norm_h))
                span = _CONTAINMENT_CONFIDENCE_HIGH - _CONTAINMENT_CONFIDENCE_LOW
                conf = _CONTAINMENT_CONFIDENCE_LOW + overlap * span
                if best_containment is None or conf > best_containment[1]:
                    best_containment = (idx, conf)

    if best_containment is not None:
        idx, conf = best_containment
        return ColumnMatch(
            schema_field=field_name,
            uploaded_header=headers[idx],
            confidence=round(conf, 3),
            status=MatchStatus.MATCHED,
        )

    # --- Layer 3: Fuzzy matching via difflib ---
    candidates: list[tuple[int, float]] = []
    for idx, norm_h in enumerate(norm_headers):
        if idx in claimed:
            continue
        # Compare against all aliases and take the best ratio
        best_ratio = 0.0
        for alias in norm_aliases:
            ratio = difflib.SequenceMatcher(None, norm_h, alias).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
        if best_ratio >= _FUZZY_THRESHOLD:
            candidates.append((idx, best_ratio))

    if not candidates:
        return ColumnMatch(
            schema_field=field_name,
            uploaded_header=None,
            confidence=0.0,
            status=MatchStatus.UNMATCHED,
        )

    # Sort by ratio descending
    candidates.sort(key=lambda x: x[1], reverse=True)

    # If top candidate is clearly better (> 0.05 ahead of second), it wins
    if len(candidates) == 1 or (candidates[0][1] - candidates[1][1]) > 0.05:
        idx, ratio = candidates[0]
        return ColumnMatch(
            schema_field=field_name,
            uploaded_header=headers[idx],
            confidence=round(ratio, 3),
            status=MatchStatus.MATCHED,
        )

    # Multiple close candidates -> ambiguous
    return ColumnMatch(
        schema_field=field_name,
        uploaded_header=None,
        confidence=round(candidates[0][1], 3),
        status=MatchStatus.AMBIGUOUS,
        candidates=[headers[c[0]] for c in candidates],
    )
