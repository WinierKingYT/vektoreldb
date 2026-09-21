import os
from uuid import uuid4

import pytest
from qdrant_client.http import models

from personal_vector_db.storage import QdrantQuantizedVectorStore, QdrantVectorStore

pytestmark = pytest.mark.integration


def test_server_qdrant_payload_indexes_and_lifecycle() -> None:
    url = os.getenv("VDB_QDRANT_URL", "")
    if not url.startswith(("http://", "https://")):
        pytest.skip("set VDB_QDRANT_URL to a running server Qdrant for integration tests")

    collection = f"vdb_integration_{uuid4().hex}"
    store = QdrantVectorStore(url, collection, timeout=60)
    try:
        store.ensure_collection(3)
        assert store.client.get_collection(collection).config.hnsw_config is not None
        schema = store.client.get_collection(collection).payload_schema
        assert {"document_id", "owner_id", "document_status"}.issubset(schema)

        store.upsert(
            [
                models.PointStruct(
                    id=str(uuid4()),
                    vector=[1.0, 0.0, 0.0],
                    payload={
                        "document_id": "doc_integration",
                        "chunk_id": "chunk_integration",
                        "owner_id": "me",
                        "document_status": "active",
                    },
                )
            ]
        )
        assert store.search([1.0, 0.0, 0.0], limit=1)[0].payload["chunk_id"] == "chunk_integration"

        store.delete_document("doc_integration")
        assert store.search([1.0, 0.0, 0.0], limit=1) == []
    finally:
        store.client.delete_collection(collection)
        store.close()


def test_server_qdrant_snapshot_restore_round_trip() -> None:
    url = os.getenv("VDB_QDRANT_URL", "")
    if not url.startswith(("http://", "https://")):
        pytest.skip("set VDB_QDRANT_URL to a running server Qdrant for integration tests")

    collection = f"vdb_snapshot_{uuid4().hex}"
    store = QdrantVectorStore(url, collection, timeout=60)
    try:
        store.ensure_collection(3)
        store.upsert(
            [
                models.PointStruct(
                    id=str(uuid4()),
                    vector=[1.0, 0.0, 0.0],
                    payload={
                        "document_id": "doc_snapshot",
                        "chunk_id": "chunk_snapshot",
                        "owner_id": "me",
                        "document_status": "active",
                    },
                )
            ]
        )
        snapshot_name = store.create_snapshot()
        checksum = getattr(store, "last_snapshot_checksum", None)
        assert snapshot_name

        store.client.delete_collection(collection)

        snapshot_location = (
            f"file:///qdrant/snapshots/{collection}/{snapshot_name}"
        )
        assert store.restore_snapshot(snapshot_location, checksum=checksum) is True
        assert store.search([1.0, 0.0, 0.0], limit=1)[0].payload["chunk_id"] == "chunk_snapshot"
    finally:
        store.client.delete_collection(collection)
        store.close()


def test_server_qdrant_quantization_configuration_and_search() -> None:
    url = os.getenv("VDB_QDRANT_URL", "")
    if not url.startswith(("http://", "https://")):
        pytest.skip("set VDB_QDRANT_URL to a running server Qdrant for integration tests")

    collection = f"vdb_quantized_{uuid4().hex}"
    store = QdrantQuantizedVectorStore(url, collection, timeout=60)
    try:
        store.ensure_collection(3)
        assert store.client.get_collection(collection).config.quantization_config is not None
        store.upsert(
            [
                models.PointStruct(
                    id=str(uuid4()),
                    vector=[1.0, 0.0, 0.0],
                    payload={
                        "document_id": "doc_quantized",
                        "chunk_id": "chunk_quantized",
                        "text": "quantized smoke",
                        "source_uri": "file:///quantized.md",
                        "title": "Quantized",
                        "location": {},
                        "embedding_manifest_id": "test:model@r1",
                        "owner_id": "me",
                        "document_status": "active",
                    },
                )
            ]
        )
        assert store.search([1.0, 0.0, 0.0], limit=1)[0].payload["chunk_id"] == "chunk_quantized"
    finally:
        store.client.delete_collection(collection)
        store.close()
