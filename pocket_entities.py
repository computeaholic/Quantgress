"""Evidence-gated recipient-to-public-parent resolution.

USAspending names the legal recipient, which is often a subsidiary.  A name
similarity is not evidence that the recipient belongs to a listed parent, so
this module accepts only explicit, cited aliases.  Unknowns stay unknown.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path


def normalize_legal_name(value: str | None) -> str:
    text = (value or "").upper()
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@dataclass(frozen=True)
class EntityMatch:
    public_parent_name: str
    ticker: str
    match_method: str
    confidence: str
    evidence_url: str


class EntityAliasIndex:
    """Resolve recipients through explicit UEI or exact legal-name aliases."""

    def __init__(self, rows):
        self._by_uei = {}
        self._by_name = {}
        ambiguous_names = set()
        for raw in rows:
            row = {key: (value or "").strip() for key, value in raw.items()}
            required = ("recipient_name", "public_parent_name", "ticker", "confidence", "evidence_url")
            if any(not row.get(key) for key in required):
                raise ValueError(f"entity alias missing required evidence: {row}")
            match = EntityMatch(
                public_parent_name=row["public_parent_name"],
                ticker=row["ticker"].upper(),
                match_method="",
                confidence=row["confidence"].upper(),
                evidence_url=row["evidence_url"],
            )
            uei = row.get("recipient_uei")
            if uei:
                if uei in self._by_uei and self._by_uei[uei] != match:
                    raise ValueError(f"ambiguous recipient UEI alias: {uei}")
                self._by_uei[uei] = match
            name = normalize_legal_name(row["recipient_name"])
            if name in self._by_name and self._by_name[name] != match:
                ambiguous_names.add(name)
            else:
                self._by_name[name] = match
        for name in ambiguous_names:
            self._by_name.pop(name, None)

    @classmethod
    def from_csv(cls, path):
        path = Path(path)
        if not path.exists():
            return cls([])
        with path.open(newline="", encoding="utf-8") as handle:
            return cls(csv.DictReader(handle))

    def resolve(self, recipient_name: str | None, recipient_uei: str | None):
        if recipient_uei:
            match = self._by_uei.get(recipient_uei.strip())
            if match is None:
                return None
            return EntityMatch(**{**match.__dict__, "match_method": "EXPLICIT_UEI"})
        match = self._by_name.get(normalize_legal_name(recipient_name))
        if match is None:
            return None
        return EntityMatch(**{**match.__dict__, "match_method": "EXPLICIT_LEGAL_NAME"})
