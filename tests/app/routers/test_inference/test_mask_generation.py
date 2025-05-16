# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from unittest.mock import patch

from fastapi.applications import FastAPI
from fastapi.encoders import jsonable_encoder
from starlette.testclient import TestClient

from pixano.app.models import AnnotationModel, TableInfo
from pixano.app.routers.inference.mask_generation import ImageMaskGenerationOutput
from pixano.app.settings import Settings
from pixano.datasets.dataset import Dataset
from pixano.features import CompressedRLE, SchemaGroup


sample_input_json = {
    "dataset_id": "dataset_multi_view_tracking_and_image",
    "image": {
        "data": {
            "format": "JPEG",
            "height": 640,
            "item_ref": {"id": "1", "name": "item"},
            "parent_ref": {"id": "", "name": ""},
            "url": "image_jpg.jpg",
            "width": 586,
        },
        "id": "orange_cats",
        "table_info": {"base_schema": "Image", "group": "views", "name": "image"},
    },
    "model": "model",
    "mask_table_name": "mask_image",
    "bbox": {
        "id": "",
        "created_at": "2025-05-15T13:31:08.690",
        "updated_at": "2025-05-15T13:31:08.690",
        "item_ref": {"name": "", "id": ""},
        "view_ref": {"name": "", "id": ""},
        "entity_ref": {"name": "", "id": ""},
        "source_ref": {"name": "", "id": ""},
        "coords": [10, 10, 50, 50],
        "format": "xywh",
        "is_normalized": False,
        "confidence": -1,
    },
}


@patch("pixano.app.routers.inference.mask_generation.image_mask_generation")
def test_call_mask_generation(
    mock_image_mask_generation,
    app_and_settings_with_client_copy: tuple[FastAPI, Settings, TestClient],
    dataset_multi_view_tracking_and_image: Dataset,
):
    app, settings, client = app_and_settings_with_client_copy

    expected_output = ImageMaskGenerationOutput(
        mask=AnnotationModel.from_row(
            row=CompressedRLE(counts=b"xx", size=[400, 400]),
            table_info=TableInfo(name="mask_image", group=SchemaGroup.ANNOTATION.value, base_schema="CompressedRLE"),
        )
    )
    mock_image_mask_generation.return_value = [
        CompressedRLE(id="m1", counts=b"xx", size=[400, 400], inference_metadata="{}")
    ]

    json = jsonable_encoder(sample_input_json)

    url = "/inference/tasks/mask-generation/image"

    response = client.post(url, json=json)
    assert response.status_code == 200
    assert expected_output.mask.to_row(dataset_multi_view_tracking_and_image).model_dump(
        exclude="id", exclude_timestamps=True
    ) == AnnotationModel.model_validate(response.json()["mask"]).to_row(
        dataset_multi_view_tracking_and_image
    ).model_dump(exclude="id", exclude_timestamps=True)

    dataset = Dataset.find(
        "dataset_multi_view_tracking_and_image", directory=settings.library_dir, media_dir=settings.media_dir
    )
    sources = dataset.get_data("source", limit=10)
    assert len(sources) == 4

    # Execute again to check the source is not created again.
    response = client.post(url, json=json)
    assert response.status_code == 200
    assert expected_output.mask.to_row(dataset_multi_view_tracking_and_image).model_dump(
        exclude="id", exclude_timestamps=True
    ) == AnnotationModel.model_validate(response.json()["mask"]).to_row(
        dataset_multi_view_tracking_and_image
    ).model_dump(exclude="id", exclude_timestamps=True)

    dataset = Dataset.find(
        "dataset_multi_view_tracking_and_image", directory=settings.library_dir, media_dir=settings.media_dir
    )
    sources = dataset.get_data("source", limit=10)
    assert len(sources) == 4


def test_call_image_mask_generation_error(
    app_and_settings_with_client_copy: tuple[FastAPI, Settings, TestClient],
):
    app, settings, client = app_and_settings_with_client_copy

    url = "/inference/tasks/mask-generation/image"

    # name must be an existing table name, but not the correct one
    sample_input_json["image"]["table_info"].update({"name": "mask_image"})
    json = jsonable_encoder(sample_input_json)
    response = client.post(url, json=json)
    assert response.status_code == 400
    assert response.json() == {"detail": "Image must be an image."}
