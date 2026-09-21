import hashlib
import io
import tarfile

import pytest
from qdrant_client.http import models

import personal_vector_db.storage.qdrant as qdrant_module
from personal_vector_db.contracts import EmbeddingManifest
from personal_vector_db.ingest import IngestService
from personal_vector_db.retrieval import ExactVectorStore, RetrievalService
from personal_vector_db.storage import QdrantVectorStore


class FakeProvider:
    manifest = EmbeddingManifest("test", "model", "r1", 3, "cosine", True)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]


def test_qdrant_memory_round_trip_filters_and_deletes() -> None:
    store = QdrantVectorStore(":memory:", "test_collection")
    store.ensure_collection(3)
    assert store.client.get_collection("test_collection").config.hnsw_config is not None
    store.upsert(
        [
            models.PointStruct(
                id="00000000-0000-0000-0000-000000000001",
                vector=[1.0, 0.0, 0.0],
                payload={
                    "document_id": "doc_keep",
                    "chunk_id": "chunk_keep",
                    "text": "korunacak içerik",
                    "source_uri": "file:///keep.md",
                    "title": "Keep",
                    "location": {},
                    "embedding_manifest_id": "test:model@r1",
                    "owner_id": "me",
                    "document_status": "active",
                },
            ),
            models.PointStruct(
                id="00000000-0000-0000-0000-000000000002",
                vector=[1.0, 0.0, 0.0],
                payload={
                    "document_id": "doc_other",
                    "chunk_id": "chunk_other",
                    "text": "başka içerik",
                    "source_uri": "file:///other.md",
                    "title": "Other",
                    "location": {},
                    "embedding_manifest_id": "test:model@r1",
                    "owner_id": "someone-else",
                    "document_status": "active",
                },
            ),
        ]
    )

    results = RetrievalService(FakeProvider(), store).search("bir soru")

    assert [result.document_id for result in results] == ["doc_keep"]
    store.delete_document("doc_keep")
    assert store.search([1.0, 0.0, 0.0]) == []


def test_qdrant_delete_is_scoped_to_v1_owner() -> None:
    store = QdrantVectorStore(":memory:", "delete_owner_scope")
    store.ensure_collection(3)
    store.upsert(
        [
            models.PointStruct(
                id="00000000-0000-0000-0000-000000000097",
                vector=[1.0, 0.0, 0.0],
                payload={
                    "document_id": "shared_document_id",
                    "chunk_id": "owned",
                    "embedding_manifest_id": "test:model@r1",
                    "owner_id": "me",
                    "document_status": "active",
                },
            ),
            models.PointStruct(
                id="00000000-0000-0000-0000-000000000098",
                vector=[1.0, 0.0, 0.0],
                payload={
                    "document_id": "shared_document_id",
                    "chunk_id": "other-owner",
                    "embedding_manifest_id": "test:model@r1",
                    "owner_id": "someone-else",
                    "document_status": "active",
                },
            ),
        ]
    )

    store.delete_document("shared_document_id")

    remaining = store.client.retrieve(
        collection_name="delete_owner_scope",
        ids=["00000000-0000-0000-0000-000000000098"],
    )
    assert len(remaining) == 1


def test_qdrant_manifest_compatibility_is_enforced() -> None:
    store = QdrantVectorStore(":memory:", "manifest")
    store.ensure_collection(3)
    store.upsert(
        [
            models.PointStruct(
                id="00000000-0000-0000-0000-000000000099",
                vector=[1.0, 0.0, 0.0],
                payload={"embedding_manifest_id": "model-a"},
            )
        ]
    )

    store.ensure_manifest("model-a")
    with pytest.raises(ValueError, match="manifest"):
        store.ensure_manifest("model-b")
    store.close()


def test_ingest_and_retrieval_round_trip_with_qdrant_memory(tmp_path) -> None:
    path = tmp_path / "personal.md"
    path.write_text("# Bilgi\n\nÖnemli kişisel bilgi.", encoding="utf-8")
    store = QdrantVectorStore(":memory:", "ingest_collection")
    store.ensure_collection(3)

    ingest_result = IngestService(FakeProvider(), store).ingest_file(path)
    results = RetrievalService(FakeProvider(), store).search("kişisel bilgi")

    assert ingest_result.chunk_count == 1
    assert results[0].document_id == ingest_result.document_id
    assert results[0].text == "Önemli kişisel bilgi."


def test_repeated_ingest_replaces_changed_document_chunks(tmp_path) -> None:
    path = tmp_path / "changing.md"
    path.write_text("Eski içerik.", encoding="utf-8")
    store = QdrantVectorStore(":memory:", "ingest_replace_collection")
    store.ensure_collection(3)
    service = IngestService(FakeProvider(), store)

    first = service.ingest_file(path)
    path.write_text("Yeni içerik.", encoding="utf-8")
    second = service.ingest_file(path)

    assert second.document_id == first.document_id
    points = store.client.scroll(
        collection_name="ingest_replace_collection", limit=10, with_payload=True
    )[0]
    assert len(points) == 1
    assert points[0].payload["text"] == "Yeni içerik."


def test_qdrant_local_path_persists_collection_and_points(tmp_path) -> None:
    storage_path = tmp_path / "qdrant"
    first = QdrantVectorStore(f"path:{storage_path}", "persistent_collection")
    first.ensure_collection(3)
    first.upsert(
        [
            models.PointStruct(
                id="00000000-0000-0000-0000-000000000003",
                vector=[1.0, 0.0, 0.0],
                payload={
                    "document_id": "doc_persist",
                    "chunk_id": "chunk_persist",
                    "text": "kalıcı içerik",
                    "source_uri": "file:///persist.md",
                    "title": "Persist",
                    "location": {},
                    "embedding_manifest_id": "test:model@r1",
                    "owner_id": "me",
                    "document_status": "active",
                },
            )
        ]
    )
    first.client.close()

    second = QdrantVectorStore(f"path:{storage_path}", "persistent_collection")
    assert second.search([1.0, 0.0, 0.0])[0].payload["chunk_id"] == "chunk_persist"
    second.client.close()


def test_qdrant_rejects_collection_dimension_mismatch() -> None:
    store = QdrantVectorStore(":memory:", "dimension_contract")
    store.ensure_collection(3)

    try:
        store.ensure_collection(4)
    except ValueError as error:
        assert "dimension" in str(error)
    else:
        raise AssertionError("collection dimension mismatch must be rejected")


def test_qdrant_replace_document_upserts_before_removing_stale_chunks() -> None:
    store = QdrantVectorStore(":memory:", "replace_collection")
    store.ensure_collection(3)
    store.upsert(
        [
            models.PointStruct(
                id="00000000-0000-0000-0000-000000000010",
                vector=[1.0, 0.0, 0.0],
                payload={
                    "document_id": "doc_replace",
                    "chunk_id": "old",
                    "content_hash": "sha256:" + "a" * 64,
                    "owner_id": "me",
                    "document_status": "active",
                },
            )
        ]
    )
    store.replace_document(
        "doc_replace",
        [
            models.PointStruct(
                id="00000000-0000-0000-0000-000000000011",
                vector=[0.0, 1.0, 0.0],
                payload={
                    "document_id": "doc_replace",
                    "chunk_id": "new",
                    "content_hash": "sha256:" + "b" * 64,
                    "owner_id": "me",
                    "document_status": "active",
                },
            )
        ],
    )

    assert store.search([0.0, 1.0, 0.0], limit=2)[0].payload["chunk_id"] == "new"
    remaining_ids = {
        point.payload["chunk_id"] for point in store.search([1.0, 0.0, 0.0], limit=2)
    }
    assert "old" not in remaining_ids


def test_qdrant_replace_document_rejects_mismatched_payload_document() -> None:
    store = QdrantVectorStore(":memory:", "replace_contract")
    store.ensure_collection(3)
    point = models.PointStruct(
        id="00000000-0000-0000-0000-000000000012",
        vector=[1.0, 0.0, 0.0],
        payload={
            "document_id": "doc_other",
            "chunk_id": "chunk",
            "content_hash": "sha256:" + "c" * 64,
            "owner_id": "me",
            "document_status": "active",
        },
    )

    try:
        store.replace_document("doc_expected", [point])
    except ValueError as error:
        assert "belong" in str(error)
    else:
        raise AssertionError("replacement must reject a mismatched document payload")


def test_qdrant_accepts_optional_hnsw_search_budget() -> None:
    store = QdrantVectorStore(":memory:", "hnsw_contract", hnsw_ef=32)
    store.ensure_collection(3)
    store.upsert(
        [
            models.PointStruct(
                id="00000000-0000-0000-0000-000000000004",
                vector=[1.0, 0.0, 0.0],
                payload={
                    "document_id": "doc_hnsw",
                    "chunk_id": "chunk_hnsw",
                    "text": "hnsw",
                    "owner_id": "me",
                    "document_status": "active",
                },
            )
        ]
    )
    assert store.search([1.0, 0.0, 0.0])[0].payload["chunk_id"] == "chunk_hnsw"


def test_qdrant_hnsw_path_matches_exact_baseline_on_fixture() -> None:
    vectors = ([1.0, 0.0, 0.0], [0.8, 0.6, 0.0], [0.0, 1.0, 0.0])
    points = [
        models.PointStruct(
            id=f"00000000-0000-0000-0000-0000000000{index + 20}",
            vector=list(vector),
            payload={
                "document_id": f"doc_{index}",
                "chunk_id": f"chunk_{index}",
                "text": f"fixture {index}",
                "source_uri": f"file:///fixture-{index}.md",
                "title": "Fixture",
                "location": {},
                "embedding_manifest_id": "test:model@r1",
                "owner_id": "me",
                "document_status": "active",
            },
        )
        for index, vector in enumerate(vectors)
    ]
    exact = ExactVectorStore()
    exact.upsert(points)
    qdrant = QdrantVectorStore(":memory:", "hnsw_parity")
    qdrant.ensure_collection(3)
    qdrant.upsert(points)

    exact_ids = [hit.id for hit in exact.search([0.9, 0.4, 0.0], limit=3)]
    hnsw_ids = [hit.id for hit in qdrant.search([0.9, 0.4, 0.0], limit=3)]

    assert hnsw_ids == exact_ids
    qdrant.close()


def test_qdrant_local_snapshot_and_restore_round_trip(tmp_path) -> None:
    source_path = tmp_path / "source-qdrant"
    archive_path = tmp_path / "snapshots" / "source.tar.gz"
    source = QdrantVectorStore(f"path:{source_path}", "backup_collection")
    source.ensure_collection(3)
    source.upsert(
        [
            models.PointStruct(
                id="00000000-0000-0000-0000-000000000005",
                vector=[1.0, 0.0, 0.0],
                payload={
                    "document_id": "doc_backup",
                    "chunk_id": "chunk_backup",
                    "text": "yedek içerik",
                    "owner_id": "me",
                    "document_status": "active",
                },
            )
        ]
    )
    assert source.create_snapshot(archive_path) == archive_path.name
    assert source.search([1.0, 0.0, 0.0])[0].payload["chunk_id"] == "chunk_backup"
    source.client.close()

    restored = QdrantVectorStore(f"path:{tmp_path / 'restored-qdrant'}", "backup_collection")
    assert restored.restore_snapshot(str(archive_path)) is True
    assert restored.search([1.0, 0.0, 0.0])[0].payload["chunk_id"] == "chunk_backup"
    restored.client.close()
    reopened = QdrantVectorStore(
        f"path:{tmp_path / 'restored-qdrant'}", "backup_collection"
    )
    assert reopened.search([1.0, 0.0, 0.0])[0].payload["chunk_id"] == "chunk_backup"
    reopened.client.close()


def test_qdrant_local_restore_preserves_existing_storage_on_staging_failure(
    tmp_path, monkeypatch
) -> None:
    archive_path = tmp_path / "snapshot.tar.gz"
    source = QdrantVectorStore(f"path:{tmp_path / 'source'}", "backup_collection")
    source.ensure_collection(3)
    source.upsert(
        [
            models.PointStruct(
                id="00000000-0000-0000-0000-000000000006",
                vector=[1.0, 0.0, 0.0],
                payload={
                    "document_id": "doc_existing",
                    "chunk_id": "chunk_existing",
                    "text": "mevcut içerik",
                    "owner_id": "me",
                    "document_status": "active",
                },
            )
        ]
    )
    source.create_snapshot(archive_path)
    source.close()

    target = QdrantVectorStore(f"path:{tmp_path / 'target'}", "backup_collection")
    target.ensure_collection(3)
    target.upsert(
        [
            models.PointStruct(
                id="00000000-0000-0000-0000-000000000007",
                vector=[1.0, 0.0, 0.0],
                payload={
                    "document_id": "doc_target",
                    "chunk_id": "chunk_target",
                    "text": "korunacak içerik",
                    "owner_id": "me",
                    "document_status": "active",
                },
            )
        ]
    )

    def fail_copy(*_args, **_kwargs):
        raise OSError("staging copy failed")

    monkeypatch.setattr(qdrant_module.shutil, "copytree", fail_copy)
    with pytest.raises(OSError, match="staging copy failed"):
        target.restore_snapshot(str(archive_path))

    assert target.healthcheck() is True
    assert target.search([1.0, 0.0, 0.0])[0].payload["chunk_id"] == "chunk_target"
    target.close()


def test_qdrant_local_restore_rejects_bad_checksum(tmp_path) -> None:
    storage_path = tmp_path / "qdrant"
    archive_path = tmp_path / "snapshot.tar.gz"
    store = QdrantVectorStore(f"path:{storage_path}", "checksum_collection")
    store.ensure_collection(3)
    store.create_snapshot(archive_path)
    checksum = hashlib.sha256(archive_path.read_bytes()).hexdigest()

    restored = QdrantVectorStore(f"path:{tmp_path / 'restored'}", "checksum_collection")
    try:
        restored.restore_snapshot(str(archive_path), checksum="0" * len(checksum))
    except ValueError as error:
        assert "checksum" in str(error)
    else:
        raise AssertionError("bad snapshot checksum must be rejected")


def test_qdrant_local_restore_rejects_path_traversal_archive(tmp_path) -> None:
    archive_path = tmp_path / "unsafe.tar.gz"
    payload = b"must not be extracted"
    with tarfile.open(archive_path, "w:gz") as archive:
        member = tarfile.TarInfo("../escape.txt")
        member.size = len(payload)
        archive.addfile(member, io.BytesIO(payload))

    store = QdrantVectorStore(f"path:{tmp_path / 'restored'}", "safe_collection")
    with pytest.raises(ValueError, match="unsafe path"):
        store.restore_snapshot(str(archive_path))

    assert not (tmp_path / "escape.txt").exists()
    assert store.healthcheck() is True


def test_qdrant_local_restore_rejects_relative_traversal_archive_member(tmp_path) -> None:
    archive_path = tmp_path / "relative-unsafe.tar.gz"
    payload = b"must not be extracted"
    with tarfile.open(archive_path, "w:gz") as archive:
        member = tarfile.TarInfo("nested/../escape.txt")
        member.size = len(payload)
        archive.addfile(member, io.BytesIO(payload))

    store = QdrantVectorStore(f"path:{tmp_path / 'restored-relative-unsafe'}", "safe_collection")
    with pytest.raises(ValueError, match="unsafe path"):
        store.restore_snapshot(str(archive_path))


def test_qdrant_local_restore_rejects_symlink_archive_member(tmp_path) -> None:
    archive_path = tmp_path / "symlink.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        member = tarfile.TarInfo("link")
        member.type = tarfile.SYMTYPE
        member.linkname = "outside.txt"
        archive.addfile(member)

    store = QdrantVectorStore(f"path:{tmp_path / 'restored-symlink'}", "safe_collection")
    with pytest.raises(ValueError, match="unsafe path"):
        store.restore_snapshot(str(archive_path))


def test_qdrant_local_restore_rejects_duplicate_archive_member(tmp_path) -> None:
    archive_path = tmp_path / "duplicate.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        for payload in (b"one", b"two"):
            member = tarfile.TarInfo("duplicate.txt")
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))

    store = QdrantVectorStore(f"path:{tmp_path / 'restored-duplicate'}", "safe_collection")
    with pytest.raises(ValueError, match="unsafe path"):
        store.restore_snapshot(str(archive_path))


def test_qdrant_local_restore_rejects_special_file_archive_member(tmp_path) -> None:
    archive_path = tmp_path / "special.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        member = tarfile.TarInfo("device")
        member.type = tarfile.CHRTYPE
        member.devmajor = 1
        member.devminor = 3
        archive.addfile(member)

    store = QdrantVectorStore(f"path:{tmp_path / 'restored-special'}", "safe_collection")
    with pytest.raises(ValueError, match="unsafe path"):
        store.restore_snapshot(str(archive_path))
