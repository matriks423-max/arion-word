import json
from pathlib import Path
from engine.llm.fakes import FakeChat
from engine.critic import Critic

FIX = Path(__file__).parent / "fixtures"
CLEAN = json.loads((FIX / "critic_clean.json").read_text())
BAD = json.loads((FIX / "critic_contradiction.json").read_text())


def test_clean_when_all_voters_clean():
    voters = [FakeChat([CLEAN]), FakeChat([CLEAN]), FakeChat([CLEAN])]
    verdict = Critic(voters).review(episode={"title": "x"}, canon_context="")
    assert verdict.clean is True
    assert verdict.issues == []


def test_rejected_when_majority_blocking():
    voters = [FakeChat([BAD]), FakeChat([BAD]), FakeChat([CLEAN])]
    verdict = Critic(voters).review(episode={"title": "x"}, canon_context="")
    assert verdict.clean is False
    assert any(i["kind"] == "dead_character_reuse" for i in verdict.issues)


def test_single_false_positive_does_not_stall():
    voters = [FakeChat([BAD]), FakeChat([CLEAN]), FakeChat([CLEAN])]
    verdict = Critic(voters).review(episode={"title": "x"}, canon_context="")
    assert verdict.clean is True            # 1 of 3 < majority -> passes
