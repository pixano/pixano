# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""End-to-end tests for explorer record querying: filters, sort, search, neighbors.

Uses a dataset with a custom record attribute (`caption`, `score`) and varied
splits/statuses so filtered/sorted pagination can be checked for exactness.
"""

import tempfile
from functools import lru_cache
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pixano.api.main import create_app
from pixano.api.settings import Settings, get_settings
from pixano.datasets.builders.dataset_builder import DatasetBuilder
from pixano.datasets.dataset import Dataset, DatasetInfo
from pixano.datasets.workspaces import WorkspaceType
from pixano.features import Entity, Image, Record


DATASET_ID = "query_dataset"

SPLITS = ["train", "val", "test"]
STATUSES = ["new", "validated"]
# 15 records. score has deliberate duplicates so the id tie-break is exercised.
SCORES = [0.5, 0.1, 0.5, 0.9, 0.1, 0.3, 0.5, 0.7, 0.1, 0.9, 0.2, 0.5, 0.4, 0.1, 0.8]
CAPTIONS = [
    "a red car on the road",
    "a dog in the park",
    "a blue car parked",
    "two cats sleeping",
    "a car in the rain",
    "a person walking a dog",
    "an empty road",
    "a truck and a car",
    "a cat on a wall",
    "a bicycle near a car",
    "a bus at the station",
    "a red bicycle",
    "a dog and a cat",
    "a car at night",
    "a person on a bicycle",
]


class QueryRecord(Record):
    """Record with custom filterable/searchable attributes."""

    caption: str = ""
    score: float = 0.0


class QueryBuilder(DatasetBuilder):
    def __init__(self, target_dir: Path, info: DatasetInfo):
        base = info.model_dump(include={"id", "name", "description", "size", "preview", "workspace", "storage_mode"})
        info = DatasetInfo(**base, record=QueryRecord, views={"image": Image}, entity=Entity)
        super().__init__(target_dir=target_dir, info=info)

    def generate_data(self):
        for i in range(15):
            record_id = f"record_{i:02d}"
            yield {
                self.record_table_name: QueryRecord(
                    id=record_id,
                    split=SPLITS[i % 3],
                    status=STATUSES[i % 2],
                    caption=CAPTIONS[i],
                    score=SCORES[i],
                ),
                "images": Image(
                    id=f"image_{i:02d}",
                    record_id=record_id,
                    logical_name="image",
                    uri=f"image_{i:02d}.jpg",
                    width=640,
                    height=480,
                    format="jpg",
                ),
                "entities": [],
            }


def _make_client(dataset: Dataset) -> TestClient:
    tmp = Path(tempfile.mkdtemp())
    models_dir = tmp / "models"
    models_dir.mkdir()
    settings = Settings(library_dir=str(dataset.path.parent), models_dir=str(models_dir))

    @lru_cache
    def get_settings_override():
        return settings

    app = create_app(settings)
    app.dependency_overrides[get_settings] = get_settings_override
    return TestClient(app)


@pytest.fixture(scope="module")
def client() -> TestClient:
    target = Path(tempfile.mkdtemp()) / "library" / DATASET_ID
    info = DatasetInfo(
        id=DATASET_ID,
        name=DATASET_ID,
        description="dataset for explorer query tests",
        workspace=WorkspaceType.IMAGE,
    )
    dataset = QueryBuilder(target_dir=target, info=info).build(mode="overwrite", check_integrity="none")
    dataset.create_scalar_indexes()  # index id/split/status like a real import
    return _make_client(dataset)


BASE = f"/datasets/{DATASET_ID}"


def _all_ids(client: TestClient, **params) -> list[str]:
    """Fetch every id under the given query params by paging."""
    ids: list[str] = []
    offset = 0
    while True:
        resp = client.get(f"{BASE}/records", params={**params, "limit": 4, "offset": offset})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        ids.extend(r["id"] for r in body["items"])
        offset += 4
        if offset >= body["total"]:
            break
    return ids


class TestFilterSchema:
    def test_capability_document_shape(self, client: TestClient):
        body = client.get(f"{BASE}/filters").json()
        assert body["table"] == "records"
        cols = {c["name"]: c for c in body["columns"]}
        assert cols["split"]["filterable"] and cols["split"]["sortable"]
        assert set(cols["split"]["values"]) == {"train", "val", "test"}
        assert cols["caption"]["searchable"] and cols["caption"]["source"] == "custom"
        assert cols["score"]["type"] == "float"
        assert cols["id"]["indexed"] is True  # created by create_scalar_indexes

    def test_search_models_empty_pins_09_contract(self, client: TestClient):
        # Semantic search lands in 0.9; the capability doc must advertise no models yet.
        search = client.get(f"{BASE}/filters").json()["search"]
        assert search["modes"] == ["text"]
        assert search["models"] == []


class TestFiltering:
    def test_filter_by_split(self, client: TestClient):
        body = client.get(f"{BASE}/records", params={"filter": "split:eq:train", "limit": 50}).json()
        assert body["total"] == 5
        assert all(r["split"] == "train" for r in body["items"])

    def test_and_composition(self, client: TestClient):
        body = client.get(
            f"{BASE}/records", params={"filter": ["split:eq:train", "status:eq:validated"], "limit": 50}
        ).json()
        assert all(r["split"] == "train" and r["status"] == "validated" for r in body["items"])
        assert body["total"] == len(body["items"])

    def test_numeric_filter(self, client: TestClient):
        body = client.get(f"{BASE}/records", params={"filter": "score:gte:0.7", "limit": 50}).json()
        assert body["total"] == sum(1 for s in SCORES if s >= 0.7)

    def test_non_servable_operator_still_correct(self, client: TestClient):
        # `ne` on an indexed column forces the safe full-scan path; result must be exact.
        body = client.get(f"{BASE}/records", params={"filter": "split:ne:train", "limit": 50}).json()
        assert body["total"] == 10
        assert all(r["split"] != "train" for r in body["items"])

    def test_contains_on_custom_attr(self, client: TestClient):
        body = client.get(f"{BASE}/records", params={"filter": "caption:contains:bicycle", "limit": 50}).json()
        assert body["total"] == sum(1 for c in CAPTIONS if "bicycle" in c)

    def test_free_text_search(self, client: TestClient):
        body = client.get(f"{BASE}/records", params={"q": "dog", "limit": 50}).json()
        assert body["total"] == sum(1 for c in CAPTIONS if "dog" in c)
        assert all("dog" in r["caption"].lower() for r in body["items"])


class TestSorting:
    def test_sort_desc_by_id(self, client: TestClient):
        body = client.get(f"{BASE}/records", params={"sort": "id", "order": "desc", "limit": 50}).json()
        ids = [r["id"] for r in body["items"]]
        assert ids == sorted(ids, reverse=True)

    def test_sort_by_duplicated_column_is_stable_across_pages(self, client: TestClient):
        # score has duplicates; the id tie-break must give one global order across pages.
        ids = _all_ids(client, sort="score", order="asc")
        assert len(ids) == 15
        assert len(set(ids)) == 15  # no record repeated or skipped across page boundaries
        # Reconstruct expected order: (score asc, id asc)
        expected = [f"record_{i:02d}" for i in sorted(range(15), key=lambda i: (SCORES[i], f"record_{i:02d}"))]
        assert ids == expected


class TestPaginationExactness:
    def test_pages_are_disjoint_and_cover_everything(self, client: TestClient):
        ids = _all_ids(client)
        assert sorted(ids) == [f"record_{i:02d}" for i in range(15)]

    def test_filtered_pagination_exactness(self, client: TestClient):
        ids = _all_ids(client, filter="split:eq:val")
        expected = sorted(f"record_{i:02d}" for i in range(15) if SPLITS[i % 3] == "val")
        assert sorted(ids) == expected


class TestErrorHandling:
    def test_malformed_raw_where_is_400_not_500(self, client: TestClient):
        resp = client.get(f"{BASE}/records", params={"where": "split = "})
        assert resp.status_code == 400

    def test_unknown_column_is_400(self, client: TestClient):
        resp = client.get(f"{BASE}/records", params={"filter": "nope:eq:x"})
        assert resp.status_code == 400
        assert "filters" in resp.json()["detail"].lower()

    def test_bad_operator_is_400(self, client: TestClient):
        resp = client.get(f"{BASE}/records", params={"filter": "score:contains:x"})
        assert resp.status_code == 400

    def test_deprecated_raw_where_still_works(self, client: TestClient):
        resp = client.get(f"{BASE}/records", params={"where": "split = 'train'", "limit": 50})
        assert resp.status_code == 200
        assert resp.json()["total"] == 5


class TestOpenApiContract:
    def test_no_phantom_filter_params(self, client: TestClient):
        schema = client.get("/openapi.json").json()
        op = schema["paths"][f"{BASE}/records".replace(DATASET_ID, "{dataset_id}")]["get"]
        names = {p["name"] for p in op.get("parameters", [])}
        # The six ignored FilterParams fields must not appear on the records listing.
        assert not ({"record_id", "entity_id", "view_name", "source_type", "tracklet_id", "frame_index"} & names)
        assert {"filter", "q", "sort", "order"} <= names


class TestNeighbors:
    def test_neighbors_match_paged_order(self, client: TestClient):
        ordered = _all_ids(client, sort="id", order="asc")
        target = ordered[7]
        nb = client.get(f"{BASE}/records/{target}/neighbors", params={"sort": "id", "order": "asc"}).json()
        assert nb["prev"] == ordered[6]
        assert nb["next"] == ordered[8]
        assert nb["position"] == 8
        assert nb["total"] == 15

    def test_neighbors_respect_filter(self, client: TestClient):
        ordered = _all_ids(client, filter="split:eq:train", sort="id", order="asc")
        target = ordered[1]
        nb = client.get(
            f"{BASE}/records/{target}/neighbors",
            params={"filter": "split:eq:train", "sort": "id", "order": "asc"},
        ).json()
        assert nb["prev"] == ordered[0]
        assert nb["next"] == ordered[2]
        assert nb["total"] == 5

    def test_neighbors_for_filtered_out_record(self, client: TestClient):
        # record_00 is split=train; ask for its neighbors within split=val → absent.
        nb = client.get(f"{BASE}/records/record_00/neighbors", params={"filter": "split:eq:val"}).json()
        assert nb["prev"] is None and nb["next"] is None and nb["position"] is None
