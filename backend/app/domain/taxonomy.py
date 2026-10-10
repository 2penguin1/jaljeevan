"""Hazard-tagged two-level problem taxonomy (Taneira card format). Pure domain: reads YAML only."""
import hashlib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

HAZARDS = ("drought", "flood", "heat")
DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "taxonomy.yaml"
_LIST_FIELDS = ("includes", "excludes", "examples", "keywords")


@dataclass(frozen=True)
class Taxonomy:
    l1: dict = field(hash=False)
    l2: dict = field(hash=False)  # every L2 node carries "parent"
    version: str = ""             # first 12 hex chars of the YAML's sha256

    # -- construction ---------------------------------------------------------------------------
    @classmethod
    def load(cls, path: Path | str | None = None) -> "Taxonomy":
        return _load_cached(str(path or DEFAULT_PATH))

    @staticmethod
    def validate(raw: dict) -> list[str]:
        errors: list[str] = []
        l1s = (raw or {}).get("l1")
        if not isinstance(l1s, dict) or not l1s:
            return ["taxonomy must have a non-empty 'l1' mapping"]
        for code, node in l1s.items():
            errors += [f"{code}: missing {req}" for req in ("name", "description") if not node.get(req)]
            hazards = node.get("hazards") or []
            if not hazards:
                errors.append(f"{code}: missing hazards")
            errors += [f"{code}: unknown hazard {h}" for h in hazards if h != "all" and h not in HAZARDS]
            children = node.get("l2") or {}
            if not children:
                errors.append(f"{code}: needs at least one L2")
            for l2code, child in children.items():
                if not l2code.startswith(f"{code}."):
                    errors.append(f"{l2code}: must start with '{code}.'")
                errors += [f"{l2code}: missing {req}" for req in ("name", "description") if not (child or {}).get(req)]
            for node_code, n in [(code, node), *((k, v or {}) for k, v in children.items())]:
                for list_field in _LIST_FIELDS:
                    values = n.get(list_field)
                    if values is not None and (not isinstance(values, list)
                                               or not all(isinstance(v, str) and v.strip() for v in values)):
                        errors.append(f"{node_code}: {list_field} must be a list of non-empty strings")
        return errors

    # -- queries -------------------------------------------------------------------------------
    def parent_of(self, l2_code: str) -> str | None:
        node = self.l2.get(l2_code)
        return node["parent"] if node else None

    def hazards_for(self, l1_codes) -> list[str]:
        """Hazards come only from hazard-specific categories (SUPPLY/AGRI, FLOOD, HEAT). Generic ones such as
        RELIEF or HEALTH apply to every hazard, so on their own they cannot tell which hazard a post is about."""
        return sorted({h for c in l1_codes if c in self.l1 and not self.l1[c]["generic"]
                       for h in self.l1[c]["hazards"]})

    def cards(self) -> str:
        """Category descriptions rendered for the LLM system prompt."""
        out = []
        for code, node in self.l1.items():
            out.append(f"## L1 {code} (hazards: {', '.join(node['hazards'])})\n{self._card(node)}")
            out += [f"### L2 {l2code}\n{self._card(child)}"
                    for l2code, child in self.l2.items() if child["parent"] == code]
        return "\n\n".join(out)

    @staticmethod
    def _card(node: dict) -> str:
        lines = [f"Category: {node['name']}", f"Definition: {node['description']}"]
        if node.get("includes"):
            lines.append("Includes: " + "; ".join(node["includes"]))
        if node.get("examples"):
            lines.append("Positive examples: " + " | ".join(node["examples"]))
        if node.get("excludes"):
            lines.append("Excludes: " + "; ".join(node["excludes"]))
        return "\n".join(lines)


@lru_cache
def _load_cached(path_str: str) -> Taxonomy:
    data = Path(path_str).read_bytes()
    raw = yaml.safe_load(data)
    errors = Taxonomy.validate(raw)
    if errors:
        raise ValueError("invalid taxonomy: " + "; ".join(errors))
    l1, l2 = {}, {}
    for code, node in raw["l1"].items():
        hazards = list(HAZARDS) if "all" in node["hazards"] else list(node["hazards"])
        l1[code] = {**{k: v for k, v in node.items() if k != "l2"}, "hazards": hazards,
                    "generic": "all" in node["hazards"]}
        for l2code, child in node["l2"].items():
            l2[l2code] = {**child, "parent": code}
    return Taxonomy(l1=l1, l2=l2, version=hashlib.sha256(data).hexdigest()[:12])
