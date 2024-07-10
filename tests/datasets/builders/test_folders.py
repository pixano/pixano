# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
import tempfile
from pathlib import Path

import pytest

from pixano.datasets.builders.folders import ImageFolderBuilder, VideoFolderBuilder
from pixano.datasets.builders.folders.base import FolderBaseBuilder
from pixano.datasets.dataset_library import DatasetLibrary
from pixano.datasets.dataset_schema import DatasetItem
from pixano.datasets.features import Image, Item, Video
from pixano.datasets.features.schemas.annotations.bbox import BBox
from pixano.datasets.features.schemas.annotations.keypoints import KeyPoints
from pixano.datasets.features.schemas.entities.entity import Entity
from pixano.datasets.features.types.schema_reference import EntityRef, ItemRef, ViewRef


ASSETS_DIRECTORY = Path(__file__).parent.parent.parent / "assets"

SAMPLE_DATA_PATHS = {
    "image_jpg": ASSETS_DIRECTORY / "sample_data/image_jpg.jpg",
    "image_png": ASSETS_DIRECTORY / "sample_data/image_png.png",
    "video_mp4": ASSETS_DIRECTORY / "sample_data/video_mp4.mp4",
}

VIDEO_INSTALLED = False
try:
    import ffmpeg

    ffmpeg.probe(SAMPLE_DATA_PATHS["video_mp4"])
    VIDEO_INSTALLED = True
except:  # noqa: E722
    pass


def _create_metadata_file_image(source_dir: Path, splits: list[str], num_items_per_split: list[int]):
    for split, num_items in zip(splits, num_items_per_split):
        metadata = []
        for item in range(num_items):
            metadata.append(
                {
                    "view": f"item_{item}.jpg" if item % 2 == 0 else f"item_{item}.png",
                    "metadata": f"metadata_{item}",
                }
            )
            if item % 2:
                metadata[-1]["entities"] = {
                    "bbox": [
                        [
                            0 + item / num_items,
                            0 + item / num_items,
                            (100 + item) / (100 + num_items),
                            (100 + item) / (100 + num_items),
                        ]
                    ]
                    * item,
                    "category": [("person" if item % 4 == 0 else "cat") if item % 2 else None] * item,
                }

        metadata_path = source_dir / split / "metadata.jsonl"
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        with metadata_path.open("w+") as f:
            for item in metadata:
                f.write(json.dumps(item) + "\n")


def _create_folder(samples_path: list[Path], splits: list[str], num_items_per_split: list[int]):
    source_dir = Path(tempfile.mkdtemp())
    for split, num_items in zip(splits, num_items_per_split):
        for item in range(num_items):
            sample_path = samples_path[item % len(samples_path)]
            item_path = source_dir / split / f"item_{item}{sample_path.suffix}"
            item_path.parent.mkdir(parents=True, exist_ok=True)
            item_path.symlink_to(sample_path)
    _create_metadata_file_image(source_dir, splits, num_items_per_split)
    return source_dir


@pytest.fixture
def image_folder():
    source_dir = _create_folder(
        [SAMPLE_DATA_PATHS["image_jpg"], SAMPLE_DATA_PATHS["image_png"]], ["train", "val"], [10, 5]
    )
    return source_dir


class MyEntity(Entity):
    category: str = "none"


@pytest.fixture
def image_schema():
    class Schema(DatasetItem):
        view: Image
        metadata: str
        entities: list[MyEntity]
        bbox: list[BBox]
        keypoint: list[KeyPoints]

    return Schema


@pytest.fixture
def video_schema():
    class Schema(DatasetItem):
        view: Video
        metadata: str
        entities: list[MyEntity]
        bbox: list[BBox]
        keypoint: list[KeyPoints]

    return Schema


@pytest.fixture
def video_folder():
    source_dir = _create_folder([SAMPLE_DATA_PATHS["video_mp4"]], ["train", "val"], [10, 5])
    return source_dir


@pytest.fixture
def image_folder_builder(image_folder, image_schema):
    return ImageFolderBuilder(
        image_folder, tempfile.mkdtemp(), image_schema, DatasetLibrary(name="test", description="test")
    )


@pytest.fixture
def video_folder_builder(video_folder, video_schema):
    return VideoFolderBuilder(
        video_folder, tempfile.mkdtemp(), video_schema, DatasetLibrary(name="test", description="test")
    )


class TestFolderBaseBuilder:
    def test_valid_init(self, image_folder_builder, video_folder_builder):
        assert isinstance(image_folder_builder, FolderBaseBuilder)
        assert isinstance(video_folder_builder, FolderBaseBuilder)
        assert image_folder_builder.source_dir.is_dir()
        assert image_folder_builder.target_dir.is_dir()
        assert video_folder_builder.source_dir.is_dir()
        assert video_folder_builder.target_dir.is_dir()
        assert image_folder_builder.view_name == "view"
        assert video_folder_builder.view_name == "view"
        assert image_folder_builder.view_schema == Image
        assert video_folder_builder.view_schema == Video
        assert image_folder_builder.entity_name == "entities"
        assert video_folder_builder.entity_name == "entities"
        assert image_folder_builder.entity_schema == MyEntity
        assert video_folder_builder.entity_schema == MyEntity

    def test_error_init(self) -> None:
        source_dir = Path(tempfile.mkdtemp())
        target_dir = Path(tempfile.mkdtemp())

        # test 1: schema without view
        class Schema(DatasetItem):
            metadata: str
            entities: list[MyEntity]
            bbox: list[BBox]

        with pytest.raises(ValueError, match="View and entity schemas must be defined in the schemas argument."):
            ImageFolderBuilder(source_dir, target_dir, Schema, DatasetLibrary(name="test", description="test"))

        # test 2: schema without entities
        class Schema(DatasetItem):
            view: Image
            metadata: str
            bbox: list[BBox]

        with pytest.raises(ValueError, match="View and entity schemas must be defined in the schemas argument."):
            ImageFolderBuilder(source_dir, target_dir, Schema, DatasetLibrary(name="test", description="test"))

        # test 3: schema with two views
        class Schema(DatasetItem):
            view: Image
            view2: Image
            metadata: str
            entities: list[MyEntity]
            bbox: list[BBox]

        with pytest.raises(ValueError, match="Only one view schema is supported in folder based builders."):
            ImageFolderBuilder(source_dir, target_dir, Schema, DatasetLibrary(name="test", description="test"))

        # test 4: schema with two entities
        class Schema(DatasetItem):
            view: Image
            metadata: str
            entities: list[MyEntity]
            entities2: list[MyEntity]
            bbox: list[BBox]

        with pytest.raises(ValueError, match="Only one entity schema is supported in folder based builders."):
            ImageFolderBuilder(source_dir, target_dir, Schema, DatasetLibrary(name="test", description="test"))

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

    def test_create_entities(self, image_folder_builder: ImageFolderBuilder):
        item = image_folder_builder._create_item(
            split="train",
            metadata="metadata",
        )
        view = image_folder_builder._create_view(item, image_folder_builder.source_dir / "train" / "item_0.jpg", Image)

        # test 1: one bbox infered
        entities_data = {"bbox": [[0, 0, 0.2, 0.2]]}
        entities, annotations = image_folder_builder._create_entities(item, view, entities_data)

        assert len(entities) == 1
        assert isinstance(entities[0], MyEntity)
        assert isinstance(entities[0].id, str) and len(entities[0].id) == 22
        assert entities[0] == MyEntity(
            id=entities[0].id,
            item_ref=ItemRef(id=item.id),
            view_ref=ViewRef(id=view.id, name="view"),
            category="none",
        )

        assert set(annotations.keys()) == {"bbox"}
        assert len(annotations["bbox"]) == 1
        assert annotations["bbox"][0] == BBox(
            id=annotations["bbox"][0].id,
            item_ref=ItemRef(id=item.id),
            view_ref=ViewRef(id=view.id, name="view"),
            entity_ref=EntityRef(id=entities[0].id, name="entities"),
            coords=[0, 0, 0.2, 0.2],
            format="xywh",
            is_normalized=True,
            confidence=1.0,
        )

        # test 2: one bbox not infered
        entities_data = {
            "bbox": {"coords": [0, 0, 100, 100], "format": "xyxy", "is_normalized": False, "confidence": 0.9}
        }
        entities, annotations = image_folder_builder._create_entities(item, view, entities_data)
        assert len(entities) == 1
        assert isinstance(entities[0], MyEntity)
        assert isinstance(entities[0].id, str) and len(entities[0].id) == 22
        assert entities[0] == MyEntity(
            id=entities[0].id,
            item_ref=ItemRef(id=item.id),
            view_ref=ViewRef(id=view.id, name="view"),
            category="none",
        )
        assert set(annotations.keys()) == {"bbox"}
        assert len(annotations["bbox"]) == 1
        assert annotations["bbox"][0] == BBox(
            id=annotations["bbox"][0].id,
            item_ref=ItemRef(id=item.id),
            view_ref=ViewRef(id=view.id, name="view"),
            entity_ref=EntityRef(id=entities[0].id, name="entities"),
            coords=[0, 0, 100, 100],
            format="xyxy",
            is_normalized=False,
            confidence=0.9,
        )

        # test 3: two bboxes, one infered, one not infered
        entities_data = {
            "bbox": [
                {"coords": [0, 0, 100, 100], "format": "xyxy", "is_normalized": False, "confidence": 0.5},
                [0.1, 0.1, 0.2, 0.2],
            ]
        }
        entities, annotations = image_folder_builder._create_entities(item, view, entities_data)
        assert len(entities) == 2
        assert isinstance(entities[0], MyEntity)
        assert isinstance(entities[1], MyEntity)
        assert isinstance(entities[0].id, str) and len(entities[0].id) == 22
        assert isinstance(entities[1].id, str) and len(entities[1].id) == 22
        assert entities[0] == MyEntity(
            id=entities[0].id,
            item_ref=ItemRef(id=item.id),
            view_ref=ViewRef(id=view.id, name="view"),
            category="none",
        )
        assert entities[1] == MyEntity(
            id=entities[1].id,
            item_ref=ItemRef(id=item.id),
            view_ref=ViewRef(id=view.id, name="view"),
            category="none",
        )
        assert set(annotations.keys()) == {"bbox"}
        assert len(annotations["bbox"]) == 2
        assert annotations["bbox"][0] == BBox(
            id=annotations["bbox"][0].id,
            item_ref=ItemRef(id=item.id),
            view_ref=ViewRef(id=view.id, name="view"),
            entity_ref=EntityRef(id=entities[0].id, name="entities"),
            coords=[0, 0, 100, 100],
            format="xyxy",
            is_normalized=False,
            confidence=0.5,
        )
        assert annotations["bbox"][1] == BBox(
            id=annotations["bbox"][1].id,
            item_ref=ItemRef(id=item.id),
            view_ref=ViewRef(id=view.id, name="view"),
            entity_ref=EntityRef(id=entities[1].id, name="entities"),
            coords=[0.1, 0.1, 0.2, 0.2],
            format="xywh",
            is_normalized=True,
            confidence=1.0,
        )

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
        entities, annotations = image_folder_builder._create_entities(item, view, entities_data)
        assert len(entities) == 1
        assert isinstance(entities[0], MyEntity)
        assert isinstance(entities[0].id, str) and len(entities[0].id) == 22
        assert entities[0] == MyEntity(
            id=entities[0].id,
            item_ref=ItemRef(id=item.id),
            view_ref=ViewRef(id=view.id, name="view"),
            category="person",
        )
        assert set(annotations.keys()) == {"bbox", "keypoint"}
        assert len(annotations["bbox"]) == 1
        assert len(annotations["keypoint"]) == 1
        assert annotations["bbox"][0] == BBox(
            id=annotations["bbox"][0].id,
            item_ref=ItemRef(id=item.id),
            view_ref=ViewRef(id=view.id, name="view"),
            entity_ref=EntityRef(id=entities[0].id, name="entities"),
            coords=[0, 0, 0.2, 0.2],
            format="xywh",
            is_normalized=True,
            confidence=1.0,
        )
        assert annotations["keypoint"][0] == KeyPoints(
            id=annotations["keypoint"][0].id,
            item_ref=ItemRef(id=item.id),
            view_ref=ViewRef(id=view.id, name="view"),
            entity_ref=EntityRef(id=entities[0].id, name="entities"),
            template_id="template_0",
            coords=[10, 10, 20, 20, 30, 30],
            states=["visible", "visible", "visible"],
        )

        # test 5: error infer keypoints
        entities_data = {"keypoint": [[10, 10, 20, 20, 30, 30]]}
        with pytest.raises(ValueError, match="not supported for infered entity creation."):
            entities = image_folder_builder._create_entities(item, view, entities_data)

        # test 6: error attribute not found in entity schema
        entities_data = {"bbox": [[0, 0, 0.2, 0.2]], "unknown": [0]}
        with pytest.raises(ValueError, match="Attribute unknown not found in entity schema."):
            entities = image_folder_builder._create_entities(item, view, entities_data)

    def test_generate_items(self, image_folder_builder: ImageFolderBuilder):
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
                entities: list[MyEntity] = item["entities"]
                bboxes: list[BBox] = item["bbox"]
                assert len(entities) == i
                for entity, bbox in zip(entities, bboxes, strict=True):
                    item_per_split = 10 if actual_item.split == "train" else 5
                    assert entity == MyEntity(
                        id=entity.id,
                        item_ref=ItemRef(id=actual_item.id),
                        view_ref=ViewRef(id=view.id, name="view"),
                        category="person" if i % 4 == 0 else "cat",
                    )
                    bbox = BBox(
                        id=bbox.id,
                        item_ref=ItemRef(id=actual_item.id),
                        view_ref=ViewRef(id=view.id, name="view"),
                        entity_ref=EntityRef(id=entity.id, name="entities"),
                        coords=[
                            0 + i / item_per_split,
                            0 + i / item_per_split,
                            (100 + i) / (100 + item_per_split),
                            (100 + i) / (100 + item_per_split),
                        ],
                        format="xywh",
                        is_normalized=True,
                        confidence=1.0,
                    )
            else:  # no entities
                assert "entities" not in item
                assert "bbox" not in item
