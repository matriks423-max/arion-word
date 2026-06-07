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


# --- fail-closed behavior (review findings: critic must not pass on a degraded panel) ---

def test_all_error_panel_fails_closed():
    # every voter raises (FakeChat([]) raises on call) -> nobody reviewed -> never clean
    verdict = Critic([FakeChat([]), FakeChat([]), FakeChat([])]).review(episode={"title": "x"}, canon_context="")
    assert verdict.clean is False


def test_quorum_not_met_fails_closed():
    # 2 of 3 error; the 1 responder says clean, but a 1/3 panel can't be trusted -> not clean
    verdict = Critic([FakeChat([]), FakeChat([]), FakeChat([CLEAN])]).review(episode={"title": "x"}, canon_context="")
    assert verdict.clean is False


def test_surviving_block_holds_when_others_error():
    verdict = Critic([FakeChat([]), FakeChat([]), FakeChat([BAD])]).review(episode={"title": "x"}, canon_context="")
    assert verdict.clean is False


def test_even_panel_tie_rejects():
    # 2 voters, 1 BAD + 1 CLEAN -> tie rejects (blocking 1 == majority 1, not < )
    verdict = Critic([FakeChat([BAD]), FakeChat([CLEAN])]).review(episode={"title": "x"}, canon_context="")
    assert verdict.clean is False


def test_even_panel_both_clean_passes():
    verdict = Critic([FakeChat([CLEAN]), FakeChat([CLEAN])]).review(episode={"title": "x"}, canon_context="")
    assert verdict.clean is True
