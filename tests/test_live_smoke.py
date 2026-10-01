import os
import pytest

pytestmark = pytest.mark.skipif(
    not (os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("NVIDIA_API_KEY")),
    reason="live keys not set",
)


def test_nvidia_embeddings_roundtrip():
    from engine.llm.nvidia_client import NvidiaEmbeddings
    vecs = NvidiaEmbeddings(api_key=os.environ["NVIDIA_API_KEY"]).embed(["hello", "world"])
    assert len(vecs) == 2 and len(vecs[0]) == 2048     # nvidia/nemotron-3-embed-1b
