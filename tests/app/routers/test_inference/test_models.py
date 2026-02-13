# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest
from fastapi.applications import FastAPI
from fastapi.testclient import TestClient

from pixano.app.settings import Settings
from pixano.inference.types import ModelInfo, ServerInfo


def get_model_info(task: str | None = None) -> list[ModelInfo]:
    models_info = [
        ModelInfo(name="model1", task="task1"),
        ModelInfo(name="model2", task="task2"),
        ModelInfo(name="model3", task="task1"),
    ]
    return [model_info for model_info in models_info if task is None or model_info.task == task]


@pytest.mark.parametrize(
    "task",
    [None, "task1"],
)
def test_list_models(
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
    task: str | None,
):
    url = "/inference/models/list"
    if task is not None:
        url += f"?task={task}"

    app, settings, client = app_and_settings_with_client

    expected_output = get_model_info(task=task)

    # Set up the mock provider's return value
    provider = settings.inference_providers[settings.default_inference_provider]
    provider.list_models.return_value = get_model_info(None)

    response = client.get(url)
    assert response.status_code == 200
    result_models = response.json()

    # Filter expected models by task if provided
    expected_names = {m.name for m in expected_output}

    if task is not None:
        # When filtering by task, result should only contain matching models
        assert all(m["task"] == task or m["name"] in expected_names for m in result_models if m["task"] == task)
    else:
        # When not filtering, we should get all models
        assert len(result_models) == len(expected_output)


def test_get_server_info(app_and_settings_with_client: tuple[FastAPI, Settings, TestClient]):
    url = "/inference/models/server-info"
    app, settings, client = app_and_settings_with_client

    # Set up the mock provider's return value
    provider = settings.inference_providers[settings.default_inference_provider]
    provider.get_server_info.return_value = ServerInfo(
        app_name="pixano-inference",
        app_version="0.5.6",
        app_description="Pixano Inference Server",
        num_cpus=8,
        num_gpus=1,
        num_nodes=1,
        gpus_used=[0],
        gpu_to_model={"0": "sam2"},
        models=["sam2", "grounding-dino"],
        models_to_task={"sam2": "image_mask_generation", "grounding-dino": "image_zero_shot_detection"},
    )

    response = client.get(url)
    assert response.status_code == 200
    result = response.json()

    assert result["app_name"] == "pixano-inference"
    assert result["app_version"] == "0.5.6"
    assert result["num_gpus"] == 1
    assert result["num_nodes"] == 1
    assert result["gpus_used"] == [0]
    assert result["models"] == ["sam2", "grounding-dino"]
    assert result["models_to_task"]["sam2"] == "image_mask_generation"
