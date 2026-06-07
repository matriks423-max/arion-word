import subprocess
import sys
from pathlib import Path


def test_validate_cli_passes_on_clean_canon(tmp_canon, tmp_path):
    # seed one valid entity by hand
    (tmp_canon / "characters").mkdir()
    (tmp_canon / "characters" / "char-ren.yaml").write_text(
        "id: char-ren\ntype: character\nname: Ren\n"
        "provenance: {introduced_episode: 1, last_changed_episode: 1, source_run: t}\n"
        "public: {role: mentor}\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "engine", "validate", "--canon", str(tmp_canon)],
        capture_output=True, text=True, cwd=Path(__file__).parent.parent)
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_validate_cli_fails_on_bad_entity(tmp_canon):
    (tmp_canon / "characters").mkdir()
    (tmp_canon / "characters" / "char-bad.yaml").write_text(
        "id: char-bad\ntype: character\nname: Bad\n"
        "provenance: {introduced_episode: 1, last_changed_episode: 1, source_run: t}\n",  # no public
        encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "engine", "validate", "--canon", str(tmp_canon)],
        capture_output=True, text=True, cwd=Path(__file__).parent.parent)
    assert result.returncode == 1
