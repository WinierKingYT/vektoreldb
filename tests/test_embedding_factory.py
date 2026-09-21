from personal_vector_db.config import Settings
from personal_vector_db.embeddings import factory


def test_factory_passes_external_embedding_settings(monkeypatch) -> None:
    captured: dict[str, object] = {}
    audit: dict[str, object] = {}

    class FakeProvider:
        def __init__(self, model_name: str, **kwargs: object) -> None:
            captured["model_name"] = model_name
            captured.update(kwargs)

    monkeypatch.setattr(factory, "OpenAIEmbeddingProvider", FakeProvider)
    monkeypatch.setattr(
        factory,
        "emit_audit_event",
        lambda event, **fields: audit.update({"event": event, **fields}),
    )
    settings = Settings(
        embedding_provider="openai",
        embedding_model="external-model",
        vector_dimension=3,
        embedding_base_url="http://localhost:9000/v1",
        embedding_timeout_seconds=7,
        embedding_max_retries=4,
        embedding_batch_size=7,
        embedding_cache_size=11,
        _env_file=None,
    )

    factory.create_embedding_provider(settings)

    assert captured["model_name"] == "external-model"
    assert captured["dimension"] == 3
    assert captured["base_url"] == "http://localhost:9000/v1"
    assert captured["timeout_seconds"] == 7
    assert captured["max_retries"] == 4
    assert captured["batch_size"] == 7
    assert captured["cache_size"] == 11
    assert audit == {
        "event": "external_embedding_provider_selected",
        "provider": "openai-compatible",
        "model": "external-model",
        "endpoint_scheme": "http",
        "endpoint_host": "localhost",
        "dimension": 3,
    }
