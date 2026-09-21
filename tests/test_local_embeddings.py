import sys
from types import SimpleNamespace

from personal_vector_db.embeddings import LocalEmbeddingProvider


class FakeModel:
    def __init__(self, dimension: int = 3) -> None:
        self.dimension = dimension
        self.calls: list[tuple[list[str], bool, bool]] = []

    def encode(self, texts: list[str], *, normalize_embeddings: bool, convert_to_numpy: bool):
        self.calls.append((texts, normalize_embeddings, convert_to_numpy))
        return [[1.0, 0.0, 0.0] for _ in texts]


def test_local_provider_keeps_query_passage_contract_and_manifest() -> None:
    model = FakeModel()
    provider = LocalEmbeddingProvider(model=model, dimension=3, revision="test-revision")

    documents = provider.embed_documents(["kişisel not"])
    query = provider.embed_query("kişisel not")

    assert documents == [[1.0, 0.0, 0.0]]
    assert query == [1.0, 0.0, 0.0]
    assert model.calls[0][0] == ["passage: kişisel not"]
    assert model.calls[1][0] == ["query: kişisel not"]
    assert model.calls[0][1:] == (True, True)
    assert provider.manifest.manifest_id.endswith(":norm=True")


def test_local_provider_passes_pinned_revision_to_model_loader(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def factory(model_name: str, *, revision: str):
        calls.append((model_name, revision))
        return FakeModel()

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=factory),
    )
    provider = LocalEmbeddingProvider(
        model_name="test-model", revision="pinned-revision", dimension=3
    )

    provider.embed_query("test")

    assert calls == [("test-model", "pinned-revision")]


def test_local_provider_rejects_wrong_dimension() -> None:
    provider = LocalEmbeddingProvider(model=FakeModel(3), dimension=2)

    try:
        provider.embed_query("test")
    except ValueError as error:
        assert "dimension" in str(error)
    else:
        raise AssertionError("dimension mismatch must be rejected")


def test_local_provider_reports_missing_model_without_library_traceback(monkeypatch) -> None:
    provider = LocalEmbeddingProvider(model=FakeModel(), dimension=3)

    def unavailable():
        raise OSError("network unavailable")

    monkeypatch.setattr(provider, "_get_model", unavailable)
    try:
        provider.embed_query("test")
    except RuntimeError as error:
        assert "complete local Hugging Face cache" in str(error)
        assert "network unavailable" not in str(error)
    else:
        raise AssertionError("missing model must produce a clear runtime error")


def test_local_provider_rejects_non_finite_vectors() -> None:
    class NonFiniteModel(FakeModel):
        def encode(self, texts, *, normalize_embeddings, convert_to_numpy):
            return [[float("nan"), 0.0, 0.0] for _ in texts]

    provider = LocalEmbeddingProvider(model=NonFiniteModel(), dimension=3)
    try:
        provider.embed_query("test")
    except ValueError as error:
        assert "non-finite" in str(error)
    else:
        raise AssertionError("non-finite embeddings must be rejected")
