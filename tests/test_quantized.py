import pytest

from personal_vector_db.storage import QdrantQuantizedVectorStore


def test_local_quantization_fails_closed_when_client_ignores_config() -> None:
    store = QdrantQuantizedVectorStore(":memory:", "quantized_test")

    with pytest.raises(RuntimeError, match="server runtime"):
        store.ensure_collection(3)
