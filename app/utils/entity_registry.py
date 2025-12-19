from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional


DEFAULT_REGISTRY_PATH = Path("data") / "entity_registry.json"


@dataclass
class EntityRegistry:
    canonical: set[str] = field(default_factory=set)
    aliases: Dict[str, str] = field(default_factory=dict)
    blocked: set[str] = field(default_factory=set)
    path: Optional[Path] = None
    loaded: bool = True
    stats: Dict[str, Dict[str, int]] = field(
        default_factory=lambda: {
            "alias_hits": {},
            "blocked_hits": {},
            "canonical_hits": {},
            "unknown_hits": {},
        }
    )

    @classmethod
    def load(cls, path: Path | None = None) -> "EntityRegistry":
        registry_path = path or DEFAULT_REGISTRY_PATH
        if not registry_path.exists():
            return cls(path=registry_path, loaded=False)

        try:
            data = json.loads(registry_path.read_text(encoding="utf-8"))
        except Exception:
            return cls(path=registry_path, loaded=False)

        canonical = {cls._normalize_key(v) for v in data.get("canonical", []) if v}
        aliases = {cls._normalize_key(k): cls._normalize_key(v) for k, v in data.get("aliases", {}).items() if k and v}
        blocked = {cls._normalize_key(v) for v in data.get("blocked", []) if v is not None}
        canonical.update(aliases.values())
        return cls(canonical=canonical, aliases=aliases, blocked=blocked, path=registry_path, loaded=True)

    @staticmethod
    def _normalize_key(name: str) -> str:
        normalized = unicodedata.normalize("NFKC", str(name)).casefold()
        normalized = " ".join(normalized.split())
        return normalized.strip("-—·•・,，。.!！?？；;:'\"()（）[]【】{} ")

    def canonicalize(self, name: str | None) -> str:
        if name is None:
            return ""
        normalized = self._normalize_key(name)
        if normalized in self.blocked or normalized == "":
            self._bump("blocked_hits", normalized)
            return ""
        if normalized in self.aliases:
            target = self.aliases[normalized]
            self._bump("alias_hits", normalized)
            return target
        if normalized in self.canonical:
            self._bump("canonical_hits", normalized)
            return normalized
        self._bump("unknown_hits", normalized)
        return normalized

    def canonical_pair(self, a: str, b: str) -> tuple[str, str]:
        ca = self.canonicalize(a)
        cb = self.canonicalize(b)
        ordered = tuple(sorted((ca, cb)))
        return ordered

    def explain(self, name: str | None) -> Dict[str, str]:
        normalized = self._normalize_key(name or "")
        if normalized in self.blocked or normalized == "":
            return {
                "input": name or "",
                "normalized": normalized,
                "canonical": "",
                "alias_hit": False,
                "blocked": True,
                "reason": "blocked",
            }
        if normalized in self.aliases:
            return {
                "input": name or "",
                "normalized": normalized,
                "canonical": self.aliases[normalized],
                "alias_hit": True,
                "blocked": False,
                "reason": "alias",
            }
        canonical = normalized if normalized in self.canonical or normalized else normalized
        return {
            "input": name or "",
            "normalized": normalized,
            "canonical": canonical,
            "alias_hit": False,
            "blocked": False,
            "reason": "canonical" if canonical in self.canonical else "unknown",
        }

    def _bump(self, key: str, value: str) -> None:
        bucket = self.stats.setdefault(key, {})
        bucket[value] = bucket.get(value, 0) + 1


def identity_registry() -> EntityRegistry:
    return EntityRegistry(loaded=False)


__all__ = ["EntityRegistry", "identity_registry", "DEFAULT_REGISTRY_PATH"]
