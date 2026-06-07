from engine.llm.fakes import FakeChat
from engine.writer import Writer, Editor

EP = {
    "title": "The Clock That Stopped", "logline": "x", "summary": "y", "cliffhanger": "z",
    "scenes": [{"scene_number": 1, "prose": "..."}],
    "patch_ops": [{"op": "mark_hook_revealed", "id": "hook-001", "episode": 1}],
}


def test_writer_write_returns_episode_dict():
    w = Writer(FakeChat([EP]))
    out = w.write(episode_number=1, canon_context="canon...")
    assert out["title"] == "The Clock That Stopped"
    assert out["patch_ops"][0]["op"] == "mark_hook_revealed"


def test_writer_revise_includes_issue_feedback_in_prompt():
    chat = FakeChat([EP])
    Writer(chat).revise(episode_number=1, canon_context="c", draft=EP,
                        issues=[{"severity": "blocking", "kind": "tone", "detail": "too edgy"}])
    assert "too edgy" in chat.calls[0]["user"]


def test_editor_polish_returns_episode():
    e = Editor(FakeChat([EP]))
    assert e.polish(EP, canon_context="c")["summary"] == "y"
