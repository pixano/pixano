# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest
from pixano_inference.client import PixanoInferenceClient


@pytest.fixture(scope="session")
def simple_pixano_inference_client() -> PixanoInferenceClient:
    return PixanoInferenceClient(
        url="http://localhost:8081",
        app_name="Pixano Inference",
        app_version="0.1.0",
        app_description="Pixano Inference",
        num_cpus=4,
        num_gpus=2,
        num_nodes=1,
        gpus_used=[],
    )


@pytest.fixture()
def simple_pixano_inference_client_fn_scope() -> PixanoInferenceClient:
    return PixanoInferenceClient(
        url="http://localhost:8081",
        app_name="Pixano Inference",
        app_version="0.1.0",
        app_description="Pixano Inference",
        num_cpus=4,
        num_gpus=2,
        num_nodes=1,
        gpus_used=[],
    )
