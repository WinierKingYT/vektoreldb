import pytest

from personal_vector_db.config import Settings, validate_runtime_settings


def test_default_settings_match_v1_contract() -> None:
    settings = Settings(_env_file=None)

    assert settings.embedding_provider == "local"
    assert settings.embedding_model == "intfloat/multilingual-e5-base"
    assert settings.embedding_revision == "d128750597153bb5987e10b1c3493a34e5a4502a"
    assert settings.vector_dimension == 768
    assert settings.distance_metric == "cosine"
    assert settings.qdrant_url == "path:qdrant_storage"
    assert settings.hnsw_ef is None
    assert settings.embedding_base_url == "https://api.openai.com/v1"
    assert settings.embedding_timeout_seconds == 30.0
    assert settings.embedding_max_retries == 2
    assert settings.embedding_batch_size == 32
    assert settings.embedding_cache_size == 256
    assert settings.source_max_bytes == 10_000_000
    assert settings.source_max_files == 5_000
    assert settings.source_max_total_bytes == 1_000_000_000


def test_external_embedding_settings_are_configurable() -> None:
    settings = Settings(
        embedding_provider="openai",
        embedding_base_url="http://localhost:9000/v1",
        embedding_timeout_seconds=4,
        embedding_max_retries=4,
        embedding_batch_size=7,
        embedding_cache_size=11,
        _env_file=None,
    )

    assert settings.embedding_base_url == "http://localhost:9000/v1"
    assert settings.embedding_timeout_seconds == 4
    assert settings.embedding_max_retries == 4
    assert settings.embedding_batch_size == 7
    assert settings.embedding_cache_size == 11


def test_source_size_limit_is_configurable() -> None:
    settings = Settings(source_max_bytes=25_000_000, _env_file=None)

    assert settings.source_max_bytes == 25_000_000


def test_directory_ingest_limits_are_configurable() -> None:
    settings = Settings(
        source_max_files=250,
        source_max_total_bytes=250_000_000,
        _env_file=None,
    )

    assert settings.source_max_files == 250
    assert settings.source_max_total_bytes == 250_000_000


def test_runtime_settings_reject_non_v1_distance() -> None:
    with pytest.raises(ValueError, match="distance metric"):
        validate_runtime_settings(Settings(distance_metric="dot", _env_file=None))
