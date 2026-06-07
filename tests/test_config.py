from pathlib import Path
from engine.llm.config import load_config


def test_load_config_reads_routing(tmp_path):
    (tmp_path / "models.yaml").write_text(
        "writer: {provider: anthropic, model: claude-opus-4-8, max_tokens: 100}\n"
        "critic: {provider: nvidia, voters: [a, b, c]}\n"
        "embeddings: {provider: nvidia, model: baai/bge-m3}\n", encoding="utf-8")
    cfg = load_config(tmp_path / "models.yaml")
    assert cfg["writer"]["model"] == "claude-opus-4-8"
    assert cfg["critic"]["voters"] == ["a", "b", "c"]
