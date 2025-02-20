# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from unittest.mock import patch

import pytest
from fastapi.applications import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.testclient import TestClient
from pixano_inference.pydantic import ModelConfig, ModelInfo

from pixano.app.settings import Settings


def get_model_info(task: str | None = None):
    models_info = [
        ModelInfo(name="model1", task="task1"),
        ModelInfo(name="model2", task="task2"),
        ModelInfo(name="model3", task="task1"),
    ]
    return [model_info for model_info in models_info if task is None or model_info.task == task]


@patch("pixano.inference.PixanoInferenceClient.list_models")
@pytest.mark.parametrize(
    "task",
    [None, "task1"],
)
def test_list_models(
    mock_list_models,
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
    task: str | None,
):
    url = "/inference/models/list/"
    if task is not None:
        url += f"?task={task}"

    app, settings, client = app_and_settings_with_client

    expected_output = get_model_info(task=task)

    mock_list_models.return_value = get_model_info(None)
    response = client.get(url)
    assert response.status_code == 200
    for expected_model, model_json in zip(expected_output, response.json(), strict=True):
        model = ModelInfo.model_validate(model_json)
        assert expected_model == model


@patch("pixano.inference.PixanoInferenceClient.instantiate_model")
def test_instantiate_model(mock_instantiate_model, app_and_settings_with_client: tuple[FastAPI, Settings, TestClient]):
    url = "/inference/models/instantiate"
    app, settings, client = app_and_settings_with_client
    mock_instantiate_model.return_value = ModelInfo(name="model1", task="causal_lm")

    response = client.post(
        url,
        json=jsonable_encoder(
            {
                "config": ModelConfig(name="model1", task="causal_lm"),
                "provider": "vllm",
            }
        ),
    )
    assert response.status_code == 200
    assert response.json() == ModelInfo(name="model1", task="causal_lm").model_dump()


@patch("pixano.inference.PixanoInferenceClient.delete_model")
def test_delete_model(mock_delete_model, app_and_settings_with_client: tuple[FastAPI, Settings, TestClient]):
    url = "/inference/models/delete/model"
    app, settings, client = app_and_settings_with_client
    mock_delete_model.return_value = None

    response = client.delete(
        url,
    )
    assert response.status_code == 200
    assert response.json() is None
