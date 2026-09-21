import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from personal_vector_db.embeddings.openai import OpenAIEmbeddingProvider


class _Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, _limit: int | None = None) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_openai_provider_orders_vectors_and_preserves_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[object] = []

    def fake_urlopen(request: object, *, timeout: float) -> _Response:
        captured.append((request, timeout))
        return _Response(
            {
                "data": [
                    {"index": 1, "embedding": [0.0, 1.0]},
                    {"index": 0, "embedding": [1.0, 0.0]},
                ]
            }
        )

    monkeypatch.setattr("personal_vector_db.embeddings.openai.urlopen", fake_urlopen)
    provider = OpenAIEmbeddingProvider(
        "test-model",
        dimension=2,
        api_key="secret",
        base_url="http://localhost:9000/v1",
        timeout_seconds=4,
    )

    vectors = provider.embed_documents(["bir", "iki"])

    assert vectors == [[1.0, 0.0], [0.0, 1.0]]
    assert provider.manifest.manifest_id.startswith("openai-embeddings:test-model@api")
    request, timeout = captured[0]
    assert request.full_url == "http://localhost:9000/v1/embeddings"
    assert timeout == 4
    assert b"bir" in request.data and b"iki" in request.data


def test_openai_provider_retries_transient_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0

    def fake_urlopen(_request: object, *, timeout: float) -> _Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise OSError("temporary network failure")
        return _Response({"data": [{"index": 0, "embedding": [1.0, 0.0]}]})

    monkeypatch.setattr("personal_vector_db.embeddings.openai.urlopen", fake_urlopen)
    monkeypatch.setattr("personal_vector_db.embeddings.openai.sleep", lambda _seconds: None)
    provider = OpenAIEmbeddingProvider("test-model", dimension=2, api_key="secret", max_retries=2)

    assert provider.embed_query("soru") == [1.0, 0.0]
    assert attempts == 3


def test_openai_provider_splits_document_batches_and_preserves_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    batches: list[list[str]] = []

    def fake_urlopen(request: object, *, timeout: float) -> _Response:
        payload = json.loads(request.data.decode("utf-8"))
        batch = payload["input"]
        batches.append(batch)
        return _Response(
            {
                "data": [
                    {"index": index, "embedding": [float(index + 1), 0.0]}
                    for index, _text in enumerate(batch)
                ]
            }
        )

    monkeypatch.setattr("personal_vector_db.embeddings.openai.urlopen", fake_urlopen)
    provider = OpenAIEmbeddingProvider(
        "test-model", dimension=2, api_key="secret", batch_size=2
    )

    vectors = provider.embed_documents(["bir", "iki", "üç", "dört", "beş"])

    assert batches == [["bir", "iki"], ["üç", "dört"], ["beş"]]
    assert vectors == [[1.0, 0.0], [2.0, 0.0], [1.0, 0.0], [2.0, 0.0], [1.0, 0.0]]


def test_openai_provider_deduplicates_inputs_within_one_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[list[str]] = []

    def fake_urlopen(request: object, *, timeout: float) -> _Response:
        payload = json.loads(request.data.decode("utf-8"))
        batch = payload["input"]
        requests.append(batch)
        return _Response(
            {
                "data": [
                    {"index": index, "embedding": [float(index + 1), 0.0]}
                    for index, _text in enumerate(batch)
                ]
            }
        )

    monkeypatch.setattr("personal_vector_db.embeddings.openai.urlopen", fake_urlopen)
    provider = OpenAIEmbeddingProvider(
        "test-model", dimension=2, api_key="secret", cache_size=0
    )

    vectors = provider.embed_documents(["aynı", "diğer", "aynı", "aynı"])

    assert requests == [["aynı", "diğer"]]
    assert vectors == [[1.0, 0.0], [2.0, 0.0], [1.0, 0.0], [1.0, 0.0]]


def test_openai_provider_counts_misses_when_cache_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "personal_vector_db.embeddings.openai.urlopen",
        lambda _request, *, timeout: _Response(
            {"data": [{"index": 0, "embedding": [1.0, 0.0]}]}
        ),
    )
    provider = OpenAIEmbeddingProvider(
        "test-model", dimension=2, api_key="secret", cache_size=0
    )

    provider.embed_query("soru")

    assert provider.cache_stats == {"hits": 0, "misses": 1, "entries": 0, "capacity": 0}


def test_openai_provider_rejects_unsafe_batch_size() -> None:
    with pytest.raises(ValueError, match="batch_size"):
        OpenAIEmbeddingProvider("test-model", dimension=2, api_key="secret", batch_size=257)


def test_openai_provider_caches_vectors_without_storing_input_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    payloads: list[bytes] = []

    def fake_urlopen(request: object, *, timeout: float) -> _Response:
        nonlocal calls
        calls += 1
        payloads.append(request.data)
        return _Response({"data": [{"index": 0, "embedding": [1.0, 0.0]}]})

    monkeypatch.setattr("personal_vector_db.embeddings.openai.urlopen", fake_urlopen)
    provider = OpenAIEmbeddingProvider("test-model", dimension=2, api_key="secret")

    assert provider.embed_query("gizli sorgu") == [1.0, 0.0]
    assert provider.embed_query("gizli sorgu") == [1.0, 0.0]
    assert calls == 1
    assert provider.cache_stats == {"hits": 1, "misses": 1, "entries": 1, "capacity": 256}
    assert "gizli sorgu" not in repr(provider._cache)
    assert b"gizli sorgu" in payloads[0]


def test_openai_provider_cache_state_is_safe_for_concurrent_hits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(request: object, *, timeout: float) -> _Response:
        return _Response({"data": [{"index": 0, "embedding": [1.0, 0.0]}]})

    monkeypatch.setattr("personal_vector_db.embeddings.openai.urlopen", fake_urlopen)
    provider = OpenAIEmbeddingProvider(
        "test-model", dimension=2, api_key="secret", cache_size=2
    )
    provider.embed_query("cached")

    with ThreadPoolExecutor(max_workers=8) as executor:
        vectors = list(executor.map(lambda _: provider.embed_query("cached"), range(32)))

    assert vectors == [[1.0, 0.0]] * 32


def test_openai_provider_fails_closed_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAIEmbeddingProvider("test-model", dimension=2)


def test_openai_provider_rejects_wrong_dimension(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "personal_vector_db.embeddings.openai.urlopen",
        lambda _request, *, timeout: _Response(
            {"data": [{"index": 0, "embedding": [1.0, 0.0, 0.0]}]}
        ),
    )
    provider = OpenAIEmbeddingProvider("test-model", dimension=2, api_key="secret")

    with pytest.raises(ValueError, match="manifest"):
        provider.embed_query("soru")


@pytest.mark.parametrize(
    "record",
    [
        {"index": True, "embedding": [1.0, 0.0]},
        {"index": "0", "embedding": [1.0, 0.0]},
        {"index": 0, "embedding": [True, 0.0]},
        {"index": 0, "embedding": ["1.0", 0.0]},
    ],
)
def test_openai_provider_rejects_coercible_response_types(
    monkeypatch: pytest.MonkeyPatch, record: dict[str, object]
) -> None:
    monkeypatch.setattr(
        "personal_vector_db.embeddings.openai.urlopen",
        lambda _request, *, timeout: _Response({"data": [record]}),
    )
    provider = OpenAIEmbeddingProvider("test-model", dimension=2, api_key="secret")

    with pytest.raises(RuntimeError, match="invalid vectors"):
        provider.embed_query("soru")


def test_openai_provider_rejects_invalid_endpoint() -> None:
    with pytest.raises(ValueError, match=r"HTTPS|HTTP\(S\)"):
        OpenAIEmbeddingProvider("test-model", dimension=2, api_key="secret", base_url="not-a-url")

    for base_url in (
        "http://example.com/v1",
        "https://user:password@example.com/v1",
        "https://example.com/v1?token=secret",
        "https://example.com/v1#fragment",
    ):
        with pytest.raises(ValueError, match=r"HTTPS|HTTP\(S\)"):
            OpenAIEmbeddingProvider(
                "test-model", dimension=2, api_key="secret", base_url=base_url
            )


def test_openai_provider_rejects_oversized_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("personal_vector_db.embeddings.openai._MAX_RESPONSE_BYTES", 4)
    monkeypatch.setattr(
        "personal_vector_db.embeddings.openai.urlopen",
        lambda _request, *, timeout: _Response({"data": []}),
    )
    provider = OpenAIEmbeddingProvider("test-model", dimension=2, api_key="secret")

    with pytest.raises(RuntimeError, match="size limit"):
        provider.embed_query("soru")
