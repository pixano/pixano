# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
import tempfile
from pathlib import Path

import pytest

from pixano.datasets.builders.folders.image import ImageFolderBuilder
from pixano.datasets.builders.folders.video import VideoFolderBuilder
from pixano.datasets.builders.folders.vqa import VQAFolderBuilder
from pixano.datasets.dataset_info import DatasetInfo
from tests.assets.sample_data.metadata import SAMPLE_DATA_PATHS


def _metadata_content(mode: str, num_items: int):
    metadata = []
    if mode == "image":
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
    elif mode == "vqa":
        for item in range(num_items):
            metadata.append(
                {
                    "image": [f"item_{item}{'.jpg' if item % 2 == 0 else '.png'}"],
                    "conversations": [
                        {
                            "question": {
                                "content": "What is the greatest number ?",
                                "question_type": "multi_choice",
                                "choices": ["0", "15", "3.14", "58"],
                            },
                            "responses": [] if item % 2 == 0 else [{"content": "58"}],
                        }
                    ],
                }
            )
    elif mode == "view_mosaic_and_empty_list":
        for item in range(num_items):
            metadata.append(
                {
                    "view": [f"item_{item}.jpg", f"item_{item + 1}.jpg"] if item % 2 == 0 else [],
                }
            )

    return metadata


def _create_metadata_file(source_dir: Path, splits: list[str], num_items_per_split: list[int], mode: str):
    for split, num_items in zip(splits, num_items_per_split):
        metadata = _metadata_content(mode, num_items)
        metadata_path = source_dir / split / "metadata.jsonl"
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        with metadata_path.open("w+") as f:
            for item in metadata:
                f.write(json.dumps(item) + "\n")


def _create_folder(
    samples_path: list[Path],
    splits: list[str],
    num_items_per_split: list[int],
    with_jsonl: bool = True,
    mode: str = "image",
):
    source_dir = Path(tempfile.mkdtemp())
    for split, num_items in zip(splits, num_items_per_split):
        for item in range(num_items):
            sample_path = samples_path[item % len(samples_path)]
            item_path = source_dir / split / f"item_{item}{sample_path.suffix}"
            item_path.parent.mkdir(parents=True, exist_ok=True)
            item_path.symlink_to(sample_path)
    if with_jsonl:
        _create_metadata_file(source_dir, splits, num_items_per_split, mode)
    return source_dir


@pytest.fixture
def image_folder():
    source_dir = _create_folder(
        [SAMPLE_DATA_PATHS["image_jpg"], SAMPLE_DATA_PATHS["image_png"]], ["train", "val"], [10, 5]
    )
    return source_dir


@pytest.fixture
def image_folder_no_jsonl():
    source_dir = _create_folder(
        [SAMPLE_DATA_PATHS["image_jpg"], SAMPLE_DATA_PATHS["image_png"]], ["train", "val"], [10, 5], with_jsonl=False
    )
    return source_dir


@pytest.fixture
def video_folder():
    source_dir = _create_folder([SAMPLE_DATA_PATHS["video_mp4"]], ["train", "val"], [10, 5])
    return source_dir


@pytest.fixture
def vqa_folder():
    source_dir = _create_folder(
        [SAMPLE_DATA_PATHS["image_jpg"], SAMPLE_DATA_PATHS["image_png"]], ["train", "val"], [2, 2], mode="vqa"
    )
    return source_dir


@pytest.fixture
def edge_case_folder():
    source_dir = _create_folder(
        [SAMPLE_DATA_PATHS["image_jpg"], SAMPLE_DATA_PATHS["image_png"]],
        ["train", "val"],
        [2, 2],
        mode="view_mosaic_and_empty_list",
    )
    return source_dir


@pytest.fixture
def image_folder_builder(image_folder, dataset_item_image_bboxes_keypoints):
    return ImageFolderBuilder(
        source_dir=image_folder,
        target_dir=tempfile.mkdtemp(),
        info=DatasetInfo(name="test", description="test"),
        dataset_item=dataset_item_image_bboxes_keypoints,
    )


@pytest.fixture
def image_folder_builder_no_jsonl(image_folder_no_jsonl):
    return ImageFolderBuilder(
        source_dir=image_folder_no_jsonl,
        target_dir=tempfile.mkdtemp(),
        info=DatasetInfo(name="test", description="test"),
    )


@pytest.fixture
def vqa_folder_builder(vqa_folder):
    return VQAFolderBuilder(
        source_dir=vqa_folder,
        target_dir=tempfile.mkdtemp(),
        info=DatasetInfo(name="test", description="test"),
    )


@pytest.fixture
def edge_case_folder_builder(edge_case_folder):
    return VQAFolderBuilder(
        source_dir=edge_case_folder,
        target_dir=tempfile.mkdtemp(),
        info=DatasetInfo(name="test", description="test"),
    )


@pytest.fixture
def video_folder_builder(video_folder, dataset_item_video_bboxes_keypoint):
    return VideoFolderBuilder(
        source_dir=video_folder,
        target_dir=tempfile.mkdtemp(),
        info=DatasetInfo(name="test", description="test"),
        dataset_item=dataset_item_video_bboxes_keypoint,
    )
