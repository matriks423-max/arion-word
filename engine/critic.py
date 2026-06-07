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
            except Exception as exc:  # a voter erroring abstains (dropped from the denominator)
                results.append({"verdict": "error", "issues": [], "_error": str(exc)})

        # FAIL CLOSED. Errored voters do NOT count toward "clean" — they abstain. We require a
        # quorum of voters to actually respond before we'll trust a clean verdict, and judge the
        # majority only among responders. A degraded or fully-down panel can never pass an episode.
        total = len(self.voters)
        responded = [r for r in results if r.get("verdict") != "error"]
        quorum = math.ceil(total / 2)
        all_issues = [i for r in results for i in r.get("issues", [])]

        if len(responded) < quorum:
            # not enough functioning critics to trust a pass
            note = {"severity": "blocking", "kind": "critic_panel_degraded",
                    "detail": f"only {len(responded)}/{total} critics responded; quorum {quorum} not met"}
            return Verdict(clean=False, issues=all_issues + [note], raw=results)

        blocking_votes = sum(
            1 for r in responded
            if any(i.get("severity") == "blocking" for i in r.get("issues", []))
        )
        clean = blocking_votes < math.ceil(len(responded) / 2)
        return Verdict(clean=clean, issues=all_issues, raw=results)
