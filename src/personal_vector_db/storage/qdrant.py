"""Qdrant adapter; Qdrant-specific types stay inside this module."""

import hashlib
import shutil
import stat
import tarfile
import tempfile
from collections.abc import Sequence
from pathlib import Path, PurePosixPath
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.http import models

from personal_vector_db.retrieval import RetrievalFilter


class QdrantVectorStore:
    def __init__(
        self,
        url: str,
        collection_name: str,
        *,
        hnsw_ef: int | None = None,
        timeout: float | None = None,
    ) -> None:
        if url == ":memory:":
            self.client = QdrantClient(":memory:")
            self._local_path = None
            self._local_mode = True
        elif url.startswith("path:"):
            self._local_path = Path(url.removeprefix("path:")).resolve()
            self.client = QdrantClient(path=str(self._local_path))
            self._local_mode = True
        else:
            self._local_path = None
            client_kwargs = {} if timeout is None else {"timeout": timeout}
            self.client = QdrantClient(url=url, **client_kwargs)
            self._local_mode = False
        self.collection_name = collection_name
        self.hnsw_ef = hnsw_ef

    def close(self) -> None:
        """Release the local storage lock or close the HTTP client."""

        self.client.close()

    def healthcheck(self) -> bool:
        try:
            self.client.get_collections()
        except Exception:
            return False
        return True

    def ensure_collection(self, dimension: int) -> None:
        if not self.client.collection_exists(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
            )
        else:
            vectors = self.client.get_collection(self.collection_name).config.params.vectors
            if not isinstance(vectors, models.VectorParams):
                raise ValueError("named vectors are not supported by the V1 collection contract")
            if vectors.size != dimension:
                raise ValueError(
                    "collection dimension "
                    f"{vectors.size} does not match provider dimension {dimension}"
                )
            if vectors.distance != models.Distance.COSINE:
                raise ValueError("collection distance does not match the V1 cosine contract")
        if self._local_mode:
            return
        for field in (
            "document_id",
            "owner_id",
            "document_status",
            "source_uri",
            "source_type",
            "title",
        ):
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field,
                    field_schema=models.PayloadSchemaType.KEYWORD,
                    wait=True,
                )
            except Exception as error:
                if "already exists" not in str(error).lower():
                    raise

    def ensure_manifest(self, manifest_id: str) -> None:
        """Reject collections containing points from another embedding space."""

        if not manifest_id.strip():
            raise ValueError("embedding manifest id cannot be empty")
        if not self.client.collection_exists(self.collection_name):
            return
        offset = None
        while True:
            points, offset = self.client.scroll(
                collection_name=self.collection_name,
                limit=100,
                offset=offset,
                with_payload=["embedding_manifest_id"],
                with_vectors=False,
            )
            for point in points:
                point_manifest = (point.payload or {}).get("embedding_manifest_id")
                if point_manifest != manifest_id:
                    raise ValueError(
                        "collection embedding manifest does not match the active provider"
                    )
            if offset is None:
                return

    def upsert(self, points: Sequence[models.PointStruct]) -> None:
        self.client.upsert(collection_name=self.collection_name, points=list(points), wait=True)

    def search(
        self,
        vector: Sequence[float],
        limit: int = 10,
        filters: RetrievalFilter | None = None,
        exact: bool = False,
        quantization: models.QuantizationSearchParams | None = None,
    ) -> list[models.ScoredPoint]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        search_params = None
        if exact or self.hnsw_ef is not None:
            search_params = models.SearchParams(
                hnsw_ef=self.hnsw_ef, exact=exact, quantization=quantization
            )
        elif quantization is not None:
            search_params = models.SearchParams(quantization=quantization)
        conditions = [
            models.FieldCondition(key="owner_id", match=models.MatchValue(value="me")),
            models.FieldCondition(
                key="document_status", match=models.MatchValue(value="active")
            ),
        ]
        if filters:
            for field, values in filters.as_mapping().items():
                conditions.append(
                    models.FieldCondition(
                        key=field, match=models.MatchAny(any=list(values))
                    )
                )
        return self.client.query_points(
            collection_name=self.collection_name,
            query=list(vector),
            limit=limit,
            search_params=search_params,
            query_filter=models.Filter(
                must=conditions
            ),
            with_payload=True,
        ).points

    def filter_selectivity(self, filters: RetrievalFilter) -> float:
        active_filter = models.Filter(
            must=[
                models.FieldCondition(key="owner_id", match=models.MatchValue(value="me")),
                models.FieldCondition(
                    key="document_status", match=models.MatchValue(value="active")
                ),
            ]
        )
        total = self.client.count(
            collection_name=self.collection_name, count_filter=active_filter, exact=True
        ).count
        if not total:
            return 0.0
        for field, values in filters.as_mapping().items():
            active_filter.must.append(
                models.FieldCondition(key=field, match=models.MatchAny(any=list(values)))
            )
        matched = self.client.count(
            collection_name=self.collection_name, count_filter=active_filter, exact=True
        ).count
        return matched / total

    def delete_document(self, document_id: str) -> None:
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id", match=models.MatchValue(value=document_id)
                        ),
                        models.FieldCondition(key="owner_id", match=models.MatchValue(value="me")),
                    ]
                )
            ),
            wait=True,
        )

    def replace_document(
        self, document_id: str, points: Sequence[models.PointStruct]
    ) -> None:
        """Upsert the replacement before removing stale chunks for the document."""

        if not points:
            raise ValueError("replacement points cannot be empty")
        document_ids = {point.payload.get("document_id") for point in points}
        if document_ids != {document_id}:
            raise ValueError("replacement points must belong to document_id")
        owners = {point.payload.get("owner_id") for point in points}
        if owners != {"me"}:
            raise ValueError("replacement points must belong to the V1 owner")
        content_hashes = {point.payload.get("content_hash") for point in points}
        if len(content_hashes) != 1 or None in content_hashes:
            raise ValueError("replacement points must share one content hash")
        content_hash = next(iter(content_hashes))
        self.upsert(points)
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id", match=models.MatchValue(value=document_id)
                        ),
                        models.FieldCondition(key="owner_id", match=models.MatchValue(value="me")),
                    ],
                    must_not=[
                        models.FieldCondition(
                            key="content_hash", match=models.MatchValue(value=content_hash)
                        )
                    ],
                )
            ),
            wait=True,
        )

    def create_snapshot(self, destination: str | Path | None = None) -> str:
        if getattr(self, "_local_path", None) is not None:
            if destination is None:
                raise ValueError("local Qdrant snapshot requires a destination archive")
            archive_path = Path(destination).resolve()
            if archive_path.parent == self._local_path or self._local_path in archive_path.parents:
                raise ValueError("snapshot archive must be outside the Qdrant storage directory")
            self.client.close()
            try:
                archive_path.parent.mkdir(parents=True, exist_ok=True)
                with tarfile.open(archive_path, "w:gz") as archive:
                    for child in self._local_path.iterdir():
                        archive.add(child, arcname=child.name)
                self.last_snapshot_checksum = hashlib.sha256(archive_path.read_bytes()).hexdigest()
            finally:
                self.client = QdrantClient(path=str(self._local_path))
            return archive_path.name
        snapshot = self.client.create_snapshot(collection_name=self.collection_name, wait=True)
        if snapshot is None or not snapshot.name:
            raise RuntimeError("Qdrant did not return a snapshot name")
        self.last_snapshot_checksum = getattr(snapshot, "checksum", None)
        return snapshot.name

    def restore_snapshot(self, location: str, *, checksum: str | None = None) -> bool:
        if getattr(self, "_local_path", None) is not None:
            archive_path = Path(location).resolve()
            if not archive_path.is_file():
                raise FileNotFoundError(archive_path)
            if checksum is not None:
                digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
                if digest.lower() != checksum.lower():
                    raise ValueError("snapshot checksum mismatch")
            with tempfile.TemporaryDirectory(prefix="vdb-restore-") as temporary:
                extraction_root = Path(temporary)
                with tarfile.open(archive_path, "r:gz") as archive:
                    members = archive.getmembers()
                    member_names: set[str] = set()
                    for member in members:
                        normalized_name = member.name.replace("\\", "/")
                        target = (extraction_root / normalized_name).resolve()
                        is_windows_absolute = (
                            len(normalized_name) >= 3
                            and normalized_name[1] == ":"
                            and normalized_name[2] == "/"
                        )
                        if (
                            "\x00" in normalized_name
                            or not normalized_name
                            or normalized_name == "."
                            or PurePosixPath(normalized_name).is_absolute()
                            or is_windows_absolute
                            or ".." in PurePosixPath(normalized_name).parts
                            or normalized_name in member_names
                            or member.issym()
                            or member.islnk()
                            or not (member.isdir() or member.isfile())
                            or extraction_root not in target.parents
                        ):
                            raise ValueError("snapshot contains an unsafe path")
                        member_names.add(normalized_name)
                        file_mode = (member.mode or 0) & 0o170000
                        if stat.S_ISLNK(file_mode):
                            raise ValueError("snapshot contains an unsafe path")
                    archive.extractall(extraction_root, filter="data")
                # Keep the current client usable if archive validation or
                # extraction fails; close it only before replacing its storage.
                self.client.close()
                self._local_path.parent.mkdir(parents=True, exist_ok=True)
                staging_root = Path(
                    tempfile.mkdtemp(prefix=".vdb-restore-stage-", dir=self._local_path.parent)
                )
                staged_path = staging_root / self._local_path.name
                backup_path = self._local_path.parent / (
                    f".{self._local_path.name}.pre-restore-{uuid4().hex}"
                )
                moved_old_storage = False
                replacement_succeeded = False
                try:
                    shutil.copytree(extraction_root, staged_path)
                    if self._local_path.exists():
                        shutil.move(self._local_path, backup_path)
                        moved_old_storage = True
                    try:
                        shutil.move(staged_path, self._local_path)
                    except Exception:
                        if self._local_path.exists():
                            shutil.rmtree(self._local_path)
                        if moved_old_storage and backup_path.exists():
                            shutil.move(backup_path, self._local_path)
                        raise
                    replacement_succeeded = True
                    if backup_path.exists():
                        shutil.rmtree(backup_path)
                finally:
                    if staging_root.exists():
                        shutil.rmtree(staging_root)
                    if not replacement_succeeded:
                        self.client = QdrantClient(path=str(self._local_path))
                self.client = QdrantClient(path=str(self._local_path))
            return True
        result = self.client.recover_snapshot(
            collection_name=self.collection_name,
            location=location,
            checksum=checksum,
            wait=True,
        )
        return result is not False
