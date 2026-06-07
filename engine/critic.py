from __future__ import annotations

import json
import math
from dataclasses import dataclass

from engine.llm.base import ChatClient

_VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["clean", "issues"]},
        "issues": {"type": "array"},
    },
    "required": ["verdict", "issues"],
}

SYSTEM = (
    "You are a continuity critic for the Arion World canon. Given a proposed episode and the "
    "relevant existing canon, find any contradiction, retcon, dead-character reuse, "
    "equivalent-exchange/power-creep violation, tone break, or hook-logic error. "
    "Return JSON {\"verdict\": \"clean\"|\"issues\", \"issues\": "
    "[{\"severity\": \"blocking\"|\"minor\", \"kind\": str, \"detail\": str}]}."
)


@dataclass
class Verdict:
    clean: bool
    issues: list[dict]
    raw: list[dict]


class Critic:
    def __init__(self, voters: list[ChatClient]):
        assert voters, "critic needs at least one voter"
        self.voters = voters

    def review(self, episode: dict, canon_context: str) -> Verdict:
        user = (
            f"RELEVANT CANON:\n{canon_context}\n\n"
            f"PROPOSED EPISODE:\n{json.dumps(episode, ensure_ascii=False)[:120000]}"
        )
        results = []
        for voter in self.voters:
            try:
                results.append(voter.complete_json(SYSTEM, user, schema=_VERDICT_SCHEMA))
            except Exception as exc:  # a voter erroring counts as an abstain, logged
                results.append({"verdict": "error", "issues": [], "_error": str(exc)})

        blocking_votes = sum(
            1 for r in results
            if any(i.get("severity") == "blocking" for i in r.get("issues", []))
        )
        majority = math.ceil(len(self.voters) / 2)
        clean = blocking_votes < majority
        all_issues = [i for r in results for i in r.get("issues", [])]
        return Verdict(clean=clean, issues=all_issues, raw=results)
