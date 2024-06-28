import json
import tempfile
from pathlib import Path

import pytest

from pixano.datasets.builders.folders import ImageFolderBuilder, VideoFolderBuilder
from pixano.datasets.dataset_library import DatasetLibrary
from pixano.datasets.dataset_schema import DatasetItem
from pixano.datasets.features.schemas.image import Image
from pixano.datasets.features.schemas.item import Item
from pixano.datasets.features.schemas.object import ImageObject
from pixano.datasets.features.schemas.video import Video


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
except:
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
                metadata[-1]["objects"] = {"bbox": [[0 + item, 0 + item, 100 + item, 100 + item]] * item}

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


class MyImageObject(ImageObject):
    category: str = "none"


@pytest.fixture
def image_schema():
    class Schema(DatasetItem):
        view: Image
        metadata: str
        objects: list[MyImageObject]

    return Schema


@pytest.fixture
def video_schema():
    class Schema(DatasetItem):
        view: Video
        metadata: str
        objects: list[MyImageObject]

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
        assert view.item_id == item.id
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
        assert view.item_id == item.id
        assert view.url == "train/item_0.mp4"
        assert view.num_frames == 209
        assert round(view.fps, 2) == 29.97
        assert view.width == 320
        assert view.height == 240
        assert view.format == "mp4"
        assert round(view.duration, 2) == 6.97

    def test_create_objects(self, image_folder_builder: ImageFolderBuilder):
        item = image_folder_builder._create_item(
            split="train",
            metadata="metadata",
        )
        view = image_folder_builder._create_view(item, image_folder_builder.source_dir / "train" / "item_0.jpg", Image)

        # test 1: one bbox infered
        objects_data = {"bbox": [[0, 0, 100, 100]]}
        objects = image_folder_builder._create_objects(item, view, objects_data)
        assert len(objects) == 1
        assert isinstance(objects[0], MyImageObject)
        assert objects[0].item_id == item.id
        assert objects[0].view_id == view.id
        assert objects[0].bbox.coords == [0, 0, 100, 100]
        assert objects[0].bbox.format == "xywh"
        assert objects[0].bbox.is_normalized is True
        assert objects[0].bbox.confidence == 1.0

        # test 2: one bbox not infered
        objects_data = {
            "bbox": {"coords": [0, 0, 100, 100], "format": "xyxy", "is_normalized": False, "confidence": 0.9}
        }
        objects = image_folder_builder._create_objects(item, view, objects_data)
        assert len(objects) == 1
        assert isinstance(objects[0], MyImageObject)
        assert objects[0].item_id == item.id
        assert objects[0].view_id == view.id
        assert objects[0].bbox.coords == [0, 0, 100, 100]
        assert objects[0].bbox.format == "xyxy"
        assert objects[0].bbox.is_normalized is False
        assert objects[0].bbox.confidence == 0.9

        # test 3: two bboxes, one infered, one not infered
        objects_data = {
            "bbox": [
                {"coords": [0, 0, 100, 100], "format": "xyxy", "is_normalized": False, "confidence": 0.5},
                [10, 10, 90, 90],
            ]
        }
        objects = image_folder_builder._create_objects(item, view, objects_data)
        assert len(objects) == 2
        assert isinstance(objects[0], MyImageObject)
        assert isinstance(objects[1], MyImageObject)
        assert objects[0].item_id == item.id
        assert objects[0].view_id == view.id
        assert objects[0].bbox.coords == [0, 0, 100, 100]
        assert objects[0].bbox.format == "xyxy"
        assert objects[0].bbox.is_normalized is False
        assert objects[1].item_id == item.id
        assert objects[1].view_id == view.id
        assert objects[1].bbox.coords == [10, 10, 90, 90]
        assert objects[1].bbox.format == "xywh"
        assert objects[1].bbox.is_normalized is True

        # test 4: one bbox and one keypoint not infered and a category
        objects_data = {
            "bbox": [[0, 0, 100, 100]],
            "keypoints": [
                {
                    "template_id": "template_0",
                    "coords": [10, 10, 20, 20, 30, 30],
                    "states": ["visible", "visible", "visible"],
                }
            ],
            "category": "person",
        }
        objects = image_folder_builder._create_objects(item, view, objects_data)
        assert len(objects) == 1
        assert isinstance(objects[0], MyImageObject)
        assert objects[0].item_id == item.id
        assert objects[0].view_id == view.id
        assert objects[0].bbox.coords == [0, 0, 100, 100]
        assert objects[0].bbox.format == "xywh"
        assert objects[0].bbox.is_normalized is True
        assert objects[0].bbox.confidence == 1.0
        assert objects[0].keypoints.template_id == "template_0"
        assert objects[0].keypoints.coords == [10, 10, 20, 20, 30, 30]
        assert objects[0].keypoints.states == ["visible", "visible", "visible"]

        # test 5: error infer keypoints
        objects_data = {"keypoints": [[10, 10, 20, 20, 30, 30]]}
        with pytest.raises(ValueError, match="not supported for infered object creation."):
            objects = image_folder_builder._create_objects(item, view, objects_data)

        # test 6: error attribute not found in object schema
        objects_data = {"bbox": [[0, 0, 100, 100]], "unknown": [0]}
        with pytest.raises(ValueError, match="Attribute unknown not found in object schema."):
            objects = image_folder_builder._create_objects(item, view, objects_data)

    def test_generate_items(self, image_folder_builder: ImageFolderBuilder):
        items = list(image_folder_builder._generate_items())
        assert len(items) == 15
        assert len([item for item in items if item["item"].split == "train"]) == 10
        assert len([item for item in items if item["item"].split == "val"]) == 5
        for item in items:
            actual_item: Item = item["item"]
            view: Image = item["view"]
            i = int(actual_item.metadata.split("_")[-1])

            assert actual_item.metadata == f"metadata_{i}"

            assert view.item_id == actual_item.id
            assert view.url == f"{actual_item.split}/item_{i}.{'png' if i % 2 else 'jpg'}"

            if i % 2:
                objects: list[MyImageObject] = item["objects"]
                assert len(objects) == i
                for object in objects:
                    assert object.item_id == actual_item.id
                    assert object.view_id == view.id
                    assert object.bbox.coords == [0 + i, 0 + i, 100 + i, 100 + i]
                    assert object.bbox.format == "xywh"
                    assert object.bbox.is_normalized is True
                    assert object.bbox.confidence == 1.0
            else:
                assert "objects" not in item
