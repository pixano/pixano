# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from pixano.datasets.builders.folders import (
    FolderBaseBuilder,
    ImageFolderBuilder,
    VideoFolderBuilder,
    VQAFolderBuilder,
)
from pixano.datasets.dataset_info import DatasetInfo
from pixano.datasets.dataset_schema import DatasetItem
from pixano.features import Conversation, Entity, Image, Item, Video
from pixano.features.schemas.annotations.bbox import BBox
from pixano.features.schemas.annotations.keypoints import KeyPoints
from pixano.features.types.schema_reference import EntityRef, ItemRef, SourceRef, ViewRef
from tests.assets.sample_data.metadata import SAMPLE_DATA_PATHS


VIDEO_INSTALLED = False
try:
    import ffmpeg

    ffmpeg.probe(SAMPLE_DATA_PATHS["video_mp4"])
    VIDEO_INSTALLED = True
except:  # noqa: E722
    pass


class TestFolderBaseBuilder:
    def test_image_video_init(
        self, image_folder_builder, image_folder_builder_no_jsonl, video_folder_builder, entity_category
    ):
        assert isinstance(image_folder_builder, ImageFolderBuilder)
        assert isinstance(image_folder_builder_no_jsonl, ImageFolderBuilder)
        assert isinstance(video_folder_builder, VideoFolderBuilder)
        assert image_folder_builder.source_dir.is_dir()
        assert image_folder_builder.target_dir.is_dir()
        assert image_folder_builder_no_jsonl.source_dir.is_dir()
        assert image_folder_builder_no_jsonl.target_dir.is_dir()
        assert video_folder_builder.source_dir.is_dir()
        assert video_folder_builder.target_dir.is_dir()
        assert image_folder_builder.view_name == "view"
        assert image_folder_builder_no_jsonl.view_name == "image"
        assert video_folder_builder.view_name == "view"
        assert image_folder_builder.view_schema == Image
        assert image_folder_builder_no_jsonl.view_schema == Image
        assert video_folder_builder.view_schema == Video
        assert image_folder_builder.entity_name == "entities"
        assert image_folder_builder_no_jsonl.entity_name == "objects"
        assert video_folder_builder.entity_name == "entities"
        assert image_folder_builder.entity_schema == entity_category
        assert image_folder_builder_no_jsonl.entity_schema == Entity
        assert video_folder_builder.entity_schema == entity_category
        assert image_folder_builder.url_prefix == Path(".")

    def test_vqa_init(self, vqa_folder_builder):
        assert isinstance(vqa_folder_builder, VQAFolderBuilder)
        assert vqa_folder_builder.source_dir.is_dir()
        assert vqa_folder_builder.target_dir.is_dir()
        assert vqa_folder_builder.view_name == "image"
        assert vqa_folder_builder.view_schema == Image
        assert vqa_folder_builder.entity_name == "conversations"
        assert vqa_folder_builder.entity_schema == Conversation
        assert vqa_folder_builder.url_prefix == Path(".")

    def test_url_prefix_init(self, dataset_item_bboxes_metadata):
        source_dir = Path(tempfile.mkdtemp())
        target_dir = Path(tempfile.mkdtemp())
        urls_relative_path = source_dir.parent.parent

        ImageFolderBuilder(
            source_dir=source_dir,
            target_dir=target_dir,
            info=DatasetInfo(name="test", description="test"),
            dataset_item=dataset_item_bboxes_metadata,
            url_prefix=urls_relative_path,
        )

    def test_no_jsonl(self):
        source_dir = Path(tempfile.mkdtemp())
        target_dir = Path(tempfile.mkdtemp())
        ImageFolderBuilder(
            source_dir=source_dir,
            target_dir=target_dir,
            info=DatasetInfo(name="test", description="test"),
        )

    def test_error_init(self, entity_category) -> None:
        source_dir = Path(tempfile.mkdtemp())
        target_dir = Path(tempfile.mkdtemp())

        # test 1: no schema with FolderBaseBuilder
        with pytest.raises(ValueError, match="A schema is required."):
            FolderBaseBuilder(
                source_dir=source_dir,
                target_dir=target_dir,
                info=DatasetInfo(name="test", description="test"),
            )

        # test 2: schema without view
        class Schema(DatasetItem):
            metadata: str
            entities: list[entity_category]
            bbox: list[BBox]

        with pytest.raises(
            ValueError, match="At least one View and one Entity schema must be defined in the schemas argument."
        ):
            ImageFolderBuilder(
                source_dir=source_dir,
                target_dir=target_dir,
                info=DatasetInfo(name="test", description="test"),
                dataset_item=Schema,
            )

        # test 3: schema without entities
        class Schema(DatasetItem):
            view: Image
            metadata: str
            bbox: list[BBox]

        with pytest.raises(
            ValueError, match="At least one View and one Entity schema must be defined in the schemas argument."
        ):
            ImageFolderBuilder(
                source_dir=source_dir,
                target_dir=target_dir,
                info=DatasetInfo(name="test", description="test"),
                dataset_item=Schema,
            )

        # test 4: schema with two views
        class Schema(DatasetItem):
            view: Image
            view2: Image
            metadata: str
            entities: list[entity_category]
            bbox: list[BBox]

        with pytest.raises(ValueError, match="Only one view schema is supported in folder based builders."):
            ImageFolderBuilder(
                source_dir=source_dir,
                target_dir=target_dir,
                info=DatasetInfo(name="test", description="test"),
                dataset_item=Schema,
            )

    def test_create_item(self, image_folder_builder: ImageFolderBuilder):
        item = image_folder_builder._create_item(
            split="train",
            metadata="metadata",
        )
        assert isinstance(item, Item)
        assert item.split == "train"
        assert item.metadata == "metadata"

    def test_create_image_view(self, image_folder_builder: ImageFolderBuilder):
        item = image_folder_builder._create_item(
            split="train",
            metadata="metadata",
        )
        view = image_folder_builder._create_view(item, image_folder_builder.source_dir / "train" / "item_0.jpg", Image)

        assert isinstance(view, Image)
        assert view.item_ref == ItemRef(id=item.id)
        assert isinstance(view.id, str) and len(view.id) == 22
        assert view.url == "train/item_0.jpg"
        assert view.width == 586
        assert view.height == 640
        assert view.format == "JPEG"

    @pytest.mark.skipif(not VIDEO_INSTALLED, reason="To load video files metadata, install ffmpeg")
    def test_create_video_view(self, video_folder_builder: VideoFolderBuilder):
        item = video_folder_builder._create_item(
            split="train",
            metadata="metadata",
        )
        view = video_folder_builder._create_view(item, video_folder_builder.source_dir / "train" / "item_0.mp4", Video)

        assert isinstance(view, Video)
        assert isinstance(view.id, str) and len(view.id) == 22
        assert view.item_ref == ItemRef(id=item.id)
        assert view.url == "train/item_0.mp4"
        assert view.num_frames == 209
        assert round(view.fps, 2) == 29.97
        assert view.width == 320
        assert view.height == 240
        assert view.format == "mp4"
        assert round(view.duration, 2) == 6.97

    def test_create_entities(self, image_folder_builder: ImageFolderBuilder, entity_category):
        item = image_folder_builder._create_item(
            split="train",
            metadata="metadata",
        )
        view = image_folder_builder._create_view(item, image_folder_builder.source_dir / "train" / "item_0.jpg", Image)

        # test 1: one bbox infered
        entities_data = {"bbox": [[0, 0, 0.2, 0.2]]}
        entities, annotations = image_folder_builder._create_entities(item, view, entities_data, "source_id")

        assert len(entities) == 1
        assert isinstance(entities[0], entity_category)
        assert isinstance(entities[0].id, str) and len(entities[0].id) == 22
        assert entities[0].model_dump(exclude_timestamps=True) == entity_category(
            id=entities[0].id,
            item_ref=ItemRef(id=item.id),
            view_ref=ViewRef(id=view.id, name="view"),
            category="none",
        ).model_dump(exclude_timestamps=True)

        assert set(annotations.keys()) == {"bbox"}
        assert len(annotations["bbox"]) == 1
        assert annotations["bbox"][0].model_dump(exclude_timestamps=True) == BBox(
            id=annotations["bbox"][0].id,
            item_ref=ItemRef(id=item.id),
            view_ref=ViewRef(id=view.id, name="view"),
            entity_ref=EntityRef(id=entities[0].id, name="entities"),
            source_ref=SourceRef(id="source_id"),
            coords=[0, 0, 0.2, 0.2],
            format="xywh",
            is_normalized=True,
            confidence=1.0,
        ).model_dump(exclude_timestamps=True)

        # test 2: one bbox not infered
        entities_data = {
            "bbox": {"coords": [0, 0, 100, 100], "format": "xyxy", "is_normalized": False, "confidence": 0.9}
        }
        entities, annotations = image_folder_builder._create_entities(item, view, entities_data, "source_id")
        assert len(entities) == 1
        assert isinstance(entities[0], entity_category)
        assert isinstance(entities[0].id, str) and len(entities[0].id) == 22
        assert entities[0].model_dump(exclude_timestamps=True) == entity_category(
            id=entities[0].id,
            item_ref=ItemRef(id=item.id),
            view_ref=ViewRef(id=view.id, name="view"),
            category="none",
        ).model_dump(exclude_timestamps=True)
        assert set(annotations.keys()) == {"bbox"}
        assert len(annotations["bbox"]) == 1
        assert annotations["bbox"][0].model_dump(exclude_timestamps=True) == BBox(
            id=annotations["bbox"][0].id,
            item_ref=ItemRef(id=item.id),
            view_ref=ViewRef(id=view.id, name="view"),
            entity_ref=EntityRef(id=entities[0].id, name="entities"),
            source_ref=SourceRef(id="source_id"),
            coords=[0, 0, 100, 100],
            format="xyxy",
            is_normalized=False,
            confidence=0.9,
        ).model_dump(exclude_timestamps=True)

        # test 3: two bboxes, one infered, one not infered
        entities_data = {
            "bbox": [
                {"coords": [0, 0, 100, 100], "format": "xyxy", "is_normalized": False, "confidence": 0.5},
                [0.1, 0.1, 0.2, 0.2],
            ]
        }
        entities, annotations = image_folder_builder._create_entities(item, view, entities_data, "source_id")
        assert len(entities) == 2
        assert isinstance(entities[0], entity_category)
        assert isinstance(entities[1], entity_category)
        assert isinstance(entities[0].id, str) and len(entities[0].id) == 22
        assert isinstance(entities[1].id, str) and len(entities[1].id) == 22
        assert entities[0].model_dump(exclude_timestamps=True) == entity_category(
            id=entities[0].id,
            item_ref=ItemRef(id=item.id),
            view_ref=ViewRef(id=view.id, name="view"),
            category="none",
        ).model_dump(exclude_timestamps=True)
        assert entities[1].model_dump(exclude_timestamps=True) == entity_category(
            id=entities[1].id,
            item_ref=ItemRef(id=item.id),
            view_ref=ViewRef(id=view.id, name="view"),
            category="none",
        ).model_dump(exclude_timestamps=True)
        assert set(annotations.keys()) == {"bbox"}
        assert len(annotations["bbox"]) == 2
        assert annotations["bbox"][0].model_dump(exclude_timestamps=True) == BBox(
            id=annotations["bbox"][0].id,
            item_ref=ItemRef(id=item.id),
            view_ref=ViewRef(id=view.id, name="view"),
            entity_ref=EntityRef(id=entities[0].id, name="entities"),
            source_ref=SourceRef(id="source_id"),
            coords=[0, 0, 100, 100],
            format="xyxy",
            is_normalized=False,
            confidence=0.5,
        ).model_dump(exclude_timestamps=True)
        assert annotations["bbox"][1].model_dump(exclude_timestamps=True) == BBox(
            id=annotations["bbox"][1].id,
            item_ref=ItemRef(id=item.id),
            view_ref=ViewRef(id=view.id, name="view"),
            entity_ref=EntityRef(id=entities[1].id, name="entities"),
            source_ref=SourceRef(id="source_id"),
            coords=[0.1, 0.1, 0.2, 0.2],
            format="xywh",
            is_normalized=True,
            confidence=1.0,
        ).model_dump(exclude_timestamps=True)

        # test 4: one bbox and one keypoint not infered and a category
        entities_data = {
            "bbox": [[0, 0, 0.2, 0.2]],
            "keypoint": [
                {
                    "template_id": "template_0",
                    "coords": [10, 10, 20, 20, 30, 30],
                    "states": ["visible", "visible", "visible"],
                }
            ],
            "category": "person",
        }
        entities, annotations = image_folder_builder._create_entities(item, view, entities_data, "source_id")
        assert len(entities) == 1
        assert isinstance(entities[0], entity_category)
        assert isinstance(entities[0].id, str) and len(entities[0].id) == 22
        assert entities[0].model_dump(exclude_timestamps=True) == entity_category(
            id=entities[0].id,
            item_ref=ItemRef(id=item.id),
            view_ref=ViewRef(id=view.id, name="view"),
            category="person",
        ).model_dump(exclude_timestamps=True)
        assert set(annotations.keys()) == {"bbox", "keypoint"}
        assert len(annotations["bbox"]) == 1
        assert len(annotations["keypoint"]) == 1
        assert annotations["bbox"][0].model_dump(exclude_timestamps=True) == BBox(
            id=annotations["bbox"][0].id,
            item_ref=ItemRef(id=item.id),
            view_ref=ViewRef(id=view.id, name="view"),
            entity_ref=EntityRef(id=entities[0].id, name="entities"),
            source_ref=SourceRef(id="source_id"),
            coords=[0, 0, 0.2, 0.2],
            format="xywh",
            is_normalized=True,
            confidence=1.0,
        ).model_dump(exclude_timestamps=True)
        assert annotations["keypoint"][0].model_dump(exclude_timestamps=True) == KeyPoints(
            id=annotations["keypoint"][0].id,
            item_ref=ItemRef(id=item.id),
            view_ref=ViewRef(id=view.id, name="view"),
            entity_ref=EntityRef(id=entities[0].id, name="entities"),
            source_ref=SourceRef(id="source_id"),
            template_id="template_0",
            coords=[10, 10, 20, 20, 30, 30],
            states=["visible", "visible", "visible"],
        ).model_dump(exclude_timestamps=True)

        # test 5: error infer keypoints
        entities_data = {"keypoint": [[10, 10, 20, 20, 30, 30]]}
        with pytest.raises(ValueError, match="not supported for infered entity creation."):
            entities = image_folder_builder._create_entities(item, view, entities_data, "source_id")

        # test 6: error attribute not found in entity schema
        entities_data = {"bbox": [[0, 0, 0.2, 0.2]], "unknown": [0]}
        with pytest.raises(ValueError, match="Attribute unknown not found in entity schema."):
            entities = image_folder_builder._create_entities(item, view, entities_data, "source_id")

    def test_generate_items(self, image_folder_builder: ImageFolderBuilder, entity_category):
        with patch(
            "pixano.datasets.builders.folders.ImageFolderBuilder.add_source", lambda *args, **kwargs: "source_id"
        ):
            items = list(image_folder_builder.generate_data())
        assert len(items) == 15
        assert len([item for item in items if item["item"].split == "train"]) == 10
        assert len([item for item in items if item["item"].split == "val"]) == 5
        for item in items:
            actual_item: Item = item["item"]
            view: Image = item["view"]
            i = int(actual_item.metadata.split("_")[-1])

            assert actual_item.metadata == f"metadata_{i}"

            assert view.item_ref == ItemRef(id=actual_item.id)
            assert view.url == f"{actual_item.split}/item_{i}.{'png' if i % 2 else 'jpg'}"

            if i % 2:  # has entities
                entities: list[entity_category] = item["entities"]
                bboxes: list[BBox] = item["bbox"]
                assert len(entities) == i
                for entity, bbox in zip(entities, bboxes, strict=True):
                    item_per_split = 10 if actual_item.split == "train" else 5
                    assert entity.model_dump(exclude_timestamps=True) == entity_category(
                        id=entity.id,
                        item_ref=ItemRef(id=actual_item.id),
                        view_ref=ViewRef(id=view.id, name="view"),
                        category="person" if i % 4 == 0 else "cat",
                    ).model_dump(exclude_timestamps=True)
                    bbox.model_dump(exclude_timestamps=True) == BBox(
                        id=bbox.id,
                        item_ref=ItemRef(id=actual_item.id),
                        view_ref=ViewRef(id=view.id, name="view"),
                        entity_ref=EntityRef(id=entity.id, name="entities"),
                        source_ref=SourceRef(id="source_id"),
                        coords=[
                            0 + i / item_per_split,
                            0 + i / item_per_split,
                            (100 + i) / (100 + item_per_split),
                            (100 + i) / (100 + item_per_split),
                        ],
                        format="xywh",
                        is_normalized=True,
                        confidence=1.0,
                    ).model_dump(exclude_timestamps=True)
            else:  # no entities
                assert "entities" not in item
                assert "bbox" not in item
