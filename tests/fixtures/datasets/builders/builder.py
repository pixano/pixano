# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import tempfile
from datetime import datetime

import pytest

from pixano.datasets.builders.dataset_builder import DatasetBuilder
from pixano.datasets.dataset_info import DatasetInfo
from pixano.features import BBox, Entity, Image, Message, Record


def generate_data_item_image_bboxes_keypoint(num_rows: int, record_table_name, record_schema):
    for i in range(num_rows):
        item_id = str(i)
        image = Image(
            id=f"image_{i}",
            record_id=item_id,
            logical_name="image",
            uri=f"image_{i}.jpg",
            width=100 - i,
            height=100 + i,
            format="jpg",
            created_at=datetime(2021, 1, 1, 0, 0, 0),
            updated_at=datetime(2021, 1, 1, 0, 0, 0),
        )
        entities = []
        bboxes = []
        for j in range(0 if not (i % 2) else 2):
            entities.append(
                Entity(
                    id=f"entity_{i}_{j}",
                    record_id=item_id,
                    created_at=datetime(2021, 1, 1, 0, 0, 0),
                    updated_at=datetime(2021, 1, 1, 0, 0, 0),
                )
            )
            bboxes.append(
                BBox(
                    coords=[0, 0, 100, 100],
                    format="xywh",
                    is_normalized=False,
                    confidence=0.9,
                    id=f"bbox_{i}_{j}",
                    record_id=item_id,
                    view_id="image",
                    entity_id=f"entity_{i}_{j}",
                    source_type="model" if j % 2 == 0 else "human",
                    source_name=f"source_{j % 2}",
                    created_at=datetime(2021, 1, 1, 0, 0, 0),
                    updated_at=datetime(2021, 1, 1, 0, 0, 0),
                )
            )

        yield {
            "images": image,
            record_table_name: record_schema(
                id=item_id,
                metadata=f"metadata_{i}",
                split="train" if i % 2 else "test",
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
            ),
            "entities": entities,
            "bboxes": bboxes,
        }


def generate_data_item_vqa(num_rows: int, record_table_name, record_schema):
    for i in range(num_rows):
        item_id = str(i)
        conversation_id = f"conversation_{i}"
        image = Image(
            id=f"image_{i}",
            record_id=item_id,
            logical_name="image",
            uri=f"image_{i}.jpg",
            width=100 - i,
            height=100 + i,
            format="jpg",
            created_at=datetime(2021, 1, 1, 0, 0, 0),
            updated_at=datetime(2021, 1, 1, 0, 0, 0),
        )
        messages = [
            Message(
                id=f"message_{i}",
                record_id=item_id,
                view_id="image",
                source_type="model" if i % 2 == 0 else "human",
                source_name=f"source_{i % 2}",
                conversation_id=conversation_id,
                number=0,
                user="tester",
                content="What is the greatest number ?",
                type="QUESTION",
                choices=["0", "15", "-14", "3.14", "58"],
                question_type="SINGLE_CHOICE",
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
            )
        ]
        if i % 2 != 0:
            messages.append(
                Message(
                    id=f"message_{i}_answer",
                    record_id=item_id,
                    view_id="image",
                    source_type="model" if i % 2 == 0 else "human",
                    source_name=f"source_{i % 2}",
                    conversation_id=conversation_id,
                    number=1,
                    user="tester",
                    content="[58]",
                    type="ANSWER",
                    choices=[],
                    created_at=datetime(2021, 1, 1, 0, 0, 0),
                    updated_at=datetime(2021, 1, 1, 0, 0, 0),
                )
            )

        yield {
            "images": image,
            record_table_name: record_schema(
                id=item_id,
                split="train" if i % 2 else "test",
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
            ),
            "messages": messages,
        }


def generate_data_multi_view_tracking_and_image(num_rows: int, schemas: dict[str, type]):
    ITEM_CATEGORIES: list[str] = ["person", "cat", "dog", "car"]
    ITEM_OTHER_CATEGORIES: list[int] = [1, 2, 3, 4]
    ENTITY_CATEGORY: list[str] = [
        "child",
        "adult",
        "orange_cat",
        "black_cat",
        "labrador",
        "bulldog",
        "red_car",
        "blue_car",
    ]
    SEQUENCE_FRAME_CATEGORY = ["RGB", "Depth", "IR"]
    for i in range(num_rows):
        item_id = str(i)
        split = "train" if i <= num_rows / 2 else "test"
        categories = (ITEM_CATEGORIES[i % 4],)
        other_categories = [ITEM_OTHER_CATEGORIES[i % 4]]

        item = schemas["record"](
            id=item_id,
            categories=categories,
            other_categories=other_categories,
            split=split,
            created_at=datetime(2021, 1, 1, 0, 0, 0),
            updated_at=datetime(2021, 1, 1, 0, 0, 0),
        )

        has_video = (i % 5 > 0) or i == 0
        sequence_frames = []
        video_embeddings = []
        tracklets = []
        entities_video = []
        bboxes_video = []
        keypoints_video = []
        if has_video:
            num_frames = i % 2 + 1
            sequence_frames = [
                schemas["video"](
                    id=f"video_{i}_{j}",
                    category=SEQUENCE_FRAME_CATEGORY[i % 3],
                    timestamp=j / 10,
                    frame_index=j,
                    record_id=item_id,
                    logical_name="video",
                    uri=f"video_{i}_{j}.jpg",
                    width=100 * i,
                    height=50 * i,
                    format="JPEG",
                    created_at=datetime(2021, 1, 1, 0, 0, 0),
                    updated_at=datetime(2021, 1, 1, 0, 0, 0),
                )
                for j in range(num_frames)
            ]

            video_embeddings = [
                schemas["video_embeddings"](
                    id=f"video_embedding_{i}_{j}",
                    record_id=item_id,
                    view_id="video",
                    frame_id=sequence_frames[j].id,
                    vector=[
                        0.1 * i * j,
                        0.2 * i * j,
                        0.3 * i * j,
                        0.4 * i * j,
                        0.5 * i * j,
                        0.6 * i * j,
                        0.7 * i * j,
                        0.8 * i * j,
                    ],
                    created_at=datetime(2021, 1, 1, 0, 0, 0),
                    updated_at=datetime(2021, 1, 1, 0, 0, 0),
                )
                for j in range(num_frames)
            ]

            num_entities = i % 3
            for j in range(num_entities):
                entity_id = f"entity_video_{i}_{j}"
                tracklet_id = f"tracklet_{i}_{j}"
                entities_video.append(
                    schemas["entities_video"](
                        id=entity_id,
                        record_id=item_id,
                        created_at=datetime(2021, 1, 1, 0, 0, 0),
                        updated_at=datetime(2021, 1, 1, 0, 0, 0),
                    )
                )
                tracklets.append(
                    schemas["tracklets"](
                        id=tracklet_id,
                        record_id=item_id,
                        entity_id=entity_id,
                        source_type="model",
                        source_name="source_0",
                        view_id="video",
                        start_timestep=0,
                        end_timestep=num_frames - 1,
                        start_timestamp=0.0,
                        end_timestamp=(num_frames - 1) / 10,
                        created_at=datetime(2021, 1, 1, 0, 0, 0),
                        updated_at=datetime(2021, 1, 1, 0, 0, 0),
                    )
                )
                num_bboxes_and_keypoints = i % 4
                for frame in sequence_frames:
                    for m in range(num_bboxes_and_keypoints):
                        bboxes_video.append(
                            schemas["bboxes_video"](
                                coords=[m, m, m * 25, m * 25],
                                format="xywh",
                                is_normalized=False,
                                confidence=0.25 * m,
                                id=f"bbox_{i}_{j}_{frame.frame_index}_{m}",
                                record_id=item_id,
                                view_id="video",
                                entity_id=entity_id,
                                source_type="model",
                                source_name="source_0",
                                tracklet_id=tracklet_id,
                                frame_id=frame.id,
                                frame_index=frame.frame_index,
                                created_at=datetime(2021, 1, 1, 0, 0, 0),
                                updated_at=datetime(2021, 1, 1, 0, 0, 0),
                            )
                        )
                        keypoints_video.append(
                            schemas["keypoints_video"](
                                template_id="template_id",
                                coords=[m, m],
                                states=["visible" if m % 2 == 0 else "invisible"],
                                id=f"keypoints_video_{i}_{j}_{frame.frame_index}_{m}",
                                record_id=item_id,
                                view_id="video",
                                entity_id=entity_id,
                                source_type="human",
                                source_name="source_1",
                                tracklet_id=tracklet_id,
                                frame_id=frame.id,
                                frame_index=frame.frame_index,
                                created_at=datetime(2021, 1, 1, 0, 0, 0),
                                updated_at=datetime(2021, 1, 1, 0, 0, 0),
                            )
                        )

        has_image = (i % 3 > 0) or i == 0
        if has_image:
            image = schemas["image"](
                id=f"image_{i}",
                record_id=item_id,
                logical_name="image",
                uri=f"image_{i}.jpg",
                width=100,
                height=100,
                format="jpg",
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
            )

            entity_image = schemas["entity_image"](
                id=f"entity_image_{i}",
                record_id=item_id,
                category=ENTITY_CATEGORY[i % 4 * 2 + i % 2],
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
            )

            bbox_image = schemas["bbox_image"](
                coords=[i, i, i * 25, i * 25],
                format="xywh",
                is_normalized=False,
                confidence=(num_rows - i) / num_rows,
                is_difficult=i % 2 == 0,
                id=f"bbox_image_{i}",
                record_id=item_id,
                view_id="image",
                entity_id=f"entity_image_{i}",
                source_type="model" if i % 3 == 0 else ("human" if i % 3 == 1 else "ground_truth"),
                source_name=f"source_{i % 3}" if i % 3 != 2 else "Ground Truth",
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
            )

            mask_image = schemas["mask_image"](
                id=f"mask_image_{i}",
                record_id=item_id,
                view_id="image",
                entity_id=f"entity_image_{i}",
                size=[10, 10],
                counts=bytes(b";37000k1"),
                source_type="model" if i % 3 == 0 else ("human" if i % 3 == 1 else "ground_truth"),
                source_name=f"source_{i % 3}" if i % 3 != 2 else "Ground Truth",
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
            )

            num_keypoints = i % 4
            keypoints_image = []
            for j in range(num_keypoints):
                keypoints_image.append(
                    schemas["keypoints_image"](
                        template_id="template_id",
                        coords=[j, j],
                        states=["visible" if j % 2 == 0 else "invisible"],
                        id=f"keypoints_image_{i}_{j}",
                        record_id=item_id,
                        view_id="image",
                        entity_id=f"entity_image_{i}",
                        source_type="model" if i % 3 == 0 else ("human" if i % 3 == 1 else "ground_truth"),
                        source_name=f"source_{i % 3}" if i % 3 != 2 else "Ground Truth",
                        created_at=datetime(2021, 1, 1, 0, 0, 0),
                        updated_at=datetime(2021, 1, 1, 0, 0, 0),
                    )
                )

            image_embedding = schemas["image_embedding"](
                id=f"image_embedding_{i}",
                record_id=item_id,
                view_id="image",
                frame_id=image.id,
                vector=[0.1 * i, 0.2 * i, 0.3 * i, 0.4 * i, 0.5 * i, 0.6 * i, 0.7 * i, 0.8 * i],
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
            )
        else:
            image = None
            image_embedding = None
            entity_image = None
            bbox_image = None
            mask_image = None
            keypoints_image = []

        yield {
            "record": item,
            "video": sequence_frames,
            "image": image,
            "entity_image": entity_image,
            "entities_video": entities_video,
            "bbox_image": bbox_image,
            "mask_image": mask_image,
            "keypoints_image": keypoints_image,
            "bboxes_video": bboxes_video,
            "keypoints_video": keypoints_video,
            "tracklets": tracklets,
            "image_embedding": image_embedding,
            "video_embeddings": video_embeddings,
        }


class DatasetBuilderImageBboxesKeypoint(DatasetBuilder):
    def __init__(self, num_rows: int = 5, *args, **kwargs):
        self.num_rows = num_rows
        super().__init__(*args, **kwargs)

    def generate_data(self):
        return generate_data_item_image_bboxes_keypoint(self.num_rows, self.record_table_name, self.record_schema)


class DatasetBuilderVQA(DatasetBuilder):
    def __init__(self, num_rows: int = 4, *args, **kwargs):
        self.num_rows = num_rows
        super().__init__(*args, **kwargs)

    def generate_data(self):
        return generate_data_item_vqa(self.num_rows, self.record_table_name, self.record_schema)


class DatasetBuilderMultiViewTrackingAndImage(DatasetBuilder):
    def __init__(self, num_rows: int = 5, *args, **kwargs):
        self.num_rows = num_rows
        super().__init__(*args, **kwargs)

    def generate_data(self):
        return generate_data_multi_view_tracking_and_image(self.num_rows, self.schemas)


@pytest.fixture()
def dataset_builder_image_bboxes_keypoint(
    info_dataset_image_bboxes_keypoint,
    num_rows=5,
):
    from pathlib import Path

    return DatasetBuilderImageBboxesKeypoint(
        num_rows,
        Path(tempfile.mkdtemp()) / "dataset",
        info_dataset_image_bboxes_keypoint,
    )


@pytest.fixture()
def dataset_builder_vqa(
    info_dataset_vqa,
    num_rows=4,
):
    from pathlib import Path

    return DatasetBuilderVQA(
        num_rows,
        Path(tempfile.mkdtemp()) / "dataset",
        info_dataset_vqa,
    )


@pytest.fixture()
def dataset_builder_multi_view_tracking_and_image(
    info_dataset_multi_view_tracking_and_image: DatasetInfo,
    num_rows: int = 5,
):
    from pathlib import Path

    return DatasetBuilderMultiViewTrackingAndImage(
        num_rows,
        Path(tempfile.mkdtemp()) / "dataset",
        info_dataset_multi_view_tracking_and_image,
    )
