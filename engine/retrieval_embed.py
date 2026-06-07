from __future__ import annotations

import json
import math

from engine.canon.store import CanonStore
from engine.llm.base import EmbeddingClient


def _text_of(entity: dict) -> str:
    parts = [entity.get("name", "")]
    pub = entity.get("public", {})
    if isinstance(pub, dict):
        parts.append(json.dumps(pub, ensure_ascii=False))
    for k in ("description", "logline", "summary"):
        if k in entity:
            parts.append(str(entity[k]))
    return " ".join(p for p in parts if p)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1e-9
    nb = math.sqrt(sum(y * y for y in b)) or 1e-9
    return dot / (na * nb)


class EmbeddingRetriever:
    def __init__(self, store: CanonStore, client: EmbeddingClient):
        self.store = store
        self.client = client
        self.path = store.root / "_index" / "embeddings.jsonl"

    def build(self) -> int:
        ids, texts = [], []
        for ent in self.store.all_entities():
            ids.append(ent["id"])
            texts.append(_text_of(ent))
        vectors = self.client.embed(texts) if texts else []
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as fh:
            for eid, vec in zip(ids, vectors):
                fh.write(json.dumps({"id": eid, "vec": vec}) + "\n")
        return len(ids)

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line]

    def relevant(self, query: str, k: int = 8) -> list[str]:
        if not self.path.exists():
            # Distinguish "no entities" from "index never built": a non-empty canon with no
            # embeddings means the writer/critic would run blind. Fail loud instead.
            if any(True for _ in self.store.list_ids()):
                raise RuntimeError(
                    "embeddings index missing while canon is non-empty; run with --reindex "
                    "(or EmbeddingRetriever.build()) before retrieval")
            return []
        rows = self._load()
        if not rows:
            return []
        qvec = self.client.embed([query])[0]
        scored = [(row["id"], _cosine(qvec, row["vec"])) for row in rows]
        scored.sort(key=lambda t: t[1], reverse=True)
        return [eid for eid, _ in scored[:k]]
