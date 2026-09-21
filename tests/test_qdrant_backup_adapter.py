from types import SimpleNamespace

from personal_vector_db.storage.qdrant import QdrantVectorStore


class FakeQdrantClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def create_snapshot(self, *, collection_name: str, wait: bool):
        self.calls.append(("create_snapshot", collection_name))
        return SimpleNamespace(name="snapshot-42", checksum="sha256:42")

    def recover_snapshot(
        self, *, collection_name: str, location: str, checksum: str | None, wait: bool
    ) -> bool:
        self.calls.append(("recover_snapshot", (collection_name, location, checksum)))
        return True


def test_qdrant_snapshot_adapter_forwards_contract() -> None:
    store = object.__new__(QdrantVectorStore)
    store.client = FakeQdrantClient()
    store.collection_name = "personal_documents_v1"

    assert store.create_snapshot() == "snapshot-42"
    assert store.last_snapshot_checksum == "sha256:42"
    assert store.restore_snapshot("file:///snapshot-42", checksum="sha256:test") is True
    assert store.client.calls == [
        ("create_snapshot", "personal_documents_v1"),
        ("recover_snapshot", ("personal_documents_v1", "file:///snapshot-42", "sha256:test")),
    ]
