# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The routes describing a dataset to a client, on a dataset whose records a clustering grouped."""

from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pixano.api.main import create_app
from pixano.api.settings import Settings, get_settings
from pixano.clustering.runs import Clustering, ClusteringAlgorithm
from pixano.datasets.dataset import Dataset, DatasetInfo
from pixano.features import Image, Record
from pixano.schemas import NOISE_CLUSTER


DATASET_ID = "grouped"
#: A run of HDBSCAN over three records: one group of two, the third in none.
RUN = Clustering(
    run_id="job-1",
    algorithm=ClusteringAlgorithm.HDBSCAN,
    parameters={"min_cluster_size": 2},
    model="clip",
    clusters=1,
    noise=1,
    records=3,
    computed_at=datetime(2026, 11, 6, 15, 40, tzinfo=timezone.utc),
)
GROUPS = {"r1": 0, "r2": 0, "r3": NOISE_CLUSTER}


@pytest.fixture
def library(tmp_path: Path) -> Path:
    library = tmp_path / "library"
    dataset = Dataset.create(
        library / DATASET_ID, DatasetInfo(id=DATASET_ID, name=DATASET_ID, record=Record, views={"image": Image})
    )
    dataset.add_records({"records": [Record(id=record_id, split="train") for record_id in GROUPS]})
    dataset.write_clustering(RUN, GROUPS)
    return library


@pytest.fixture
def client(library: Path, tmp_path: Path) -> TestClient:
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    settings = Settings(library_dir=str(library), models_dir=str(models_dir))

    @lru_cache
    def settings_override() -> Settings:
        return settings

    app = create_app(settings)
    app.dependency_overrides[get_settings] = settings_override
    return TestClient(app)


class TestTheDatasetRoutesLeaveThemOut:
    """The clusters table is no table a client reads rows of, and the runs are no field of what a client
    reads of a dataset: the routes describing a dataset skip both."""

    @pytest.mark.parametrize(
        "route",
        ["/datasets", f"/datasets/{DATASET_ID}", f"/datasets/{DATASET_ID}/info", f"/datasets/{DATASET_ID}/stats"],
    )
    def test_they_answer_and_say_nothing_of_them(self, client: TestClient, route: str) -> None:
        response = client.get(route)

        assert response.status_code == 200
        leaked = [name for name in ('"clusterings"', "record_clusters") if name in response.text]
        assert leaked == []
