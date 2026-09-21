from personal_vector_db.contracts import EmbeddingManifest


def test_embedding_manifest_is_immutable() -> None:
    manifest = EmbeddingManifest("local", "model", "revision", 768, "cosine", True)

    assert manifest.dimension == 768
    assert manifest.normalized is True
