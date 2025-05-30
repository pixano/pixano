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
from pixano.datasets.dataset_schema import DatasetItem
from pixano.features import BBox, Conversation, Entity, Image, Message, Source
from pixano.features.schemas.base_schema import BaseSchema
from pixano.features.types.schema_reference import EntityRef, ItemRef, SourceRef, ViewRef


def generate_data_item_image_bboxes_keypoint(num_rows: int, item_schema_name, item_schema):
    yield {
        "source": [
            Source(id="source_0", name="source_0", kind="model", metadata={"key_0": "value_0"}),
            Source(id="source_1", name="source_1", kind="human", metadata={"key_1": "value_1"}),
        ],
    }
    for i in range(num_rows):
        item_id = str(i)
        image = Image(
            id=f"image_{i}",
            item_ref=ItemRef(id=item_id),
            url=f"image_{i}.jpg",
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
                    item_ref=ItemRef(id=item_id),
                    view_ref=ViewRef(id=f"image_{i}", name="image"),
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
                    item_ref=ItemRef(id=item_id),
                    view_ref=ViewRef(id=f"image_{i}", name="image"),
                    entity_ref=EntityRef(id=f"entity_{i}_{j}", name="entities"),
                    source_ref=SourceRef(id=f"source_{j % 2}", name="source"),
                    created_at=datetime(2021, 1, 1, 0, 0, 0),
                    updated_at=datetime(2021, 1, 1, 0, 0, 0),
                )
            )

        yield {
            "image": image,
            item_schema_name: item_schema(
                id=item_id,
                metadata=f"metadata_{i}",
                split="train" if i % 2 else "test",
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
            ),
            "entities": entities,
            "bboxes": bboxes,
        }


def generate_data_item_vqa(num_rows: int, item_schema_name, item_schema):
    yield {
        "source": [
            Source(id="source_0", name="source_0", kind="model", metadata={"key_0": "value_0"}),
            Source(id="source_1", name="source_1", kind="human", metadata={"key_1": "value_1"}),
        ],
    }
    for i in range(num_rows):
        item_id = str(i)
        image = Image(
            id=f"image_{i}",
            item_ref=ItemRef(id=item_id),
            url=f"image_{i}.jpg",
            width=100 - i,
            height=100 + i,
            format="jpg",
            created_at=datetime(2021, 1, 1, 0, 0, 0),
            updated_at=datetime(2021, 1, 1, 0, 0, 0),
        )
        conversations = []
        messages = []
        conversations.append(
            Conversation(
                id=f"conversation_{i}",
                kind="Math",
                item_ref=ItemRef(id=item_id),
                view_ref=ViewRef(id=f"image_{i}", name="image"),
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
            )
        )
        messages.append(
            Message(
                number=0,
                user="tester",
                content="What is the greatest number ?",
                type="QUESTION",
                question_type="MULTI_CHOICE",
                choices=["0", "15", "-14", "3.14", "58"],
                id=f"message_{i}",
                item_ref=ItemRef(id=item_id),
                view_ref=ViewRef(id=f"image_{i}", name="image"),
                entity_ref=EntityRef(id=f"conversation_{i}", name="conversations"),
                source_ref=SourceRef(id=f"source_{i % 2}", name="source"),
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
            )
        )
        if i % 2 != 0:
            messages.append(
                Message(
                    number=0,
                    user="tester",
                    content="[58]",
                    type="ANSWER",
                    question_type="MULTI_CHOICE",
                    choices=[],
                    id=f"message_{i}_answer",
                    item_ref=ItemRef(id=item_id),
                    view_ref=ViewRef(id=f"image_{i}", name="image"),
                    entity_ref=EntityRef(id=f"conversation_{i}", name="conversations"),
                    source_ref=SourceRef(id=f"source_{i % 2}", name="source"),
                    created_at=datetime(2021, 1, 1, 0, 0, 0),
                    updated_at=datetime(2021, 1, 1, 0, 0, 0),
                )
            )

        yield {
            "image": image,
            item_schema_name: item_schema(
                id=item_id,
                split="train" if i % 2 else "test",
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
            ),
            "conversations": conversations,
            "messages": messages,
        }


def generate_data_multi_view_tracking_and_image(num_rows: int, schemas: dict[str, BaseSchema]):
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
    yield {
        "source": [
            Source(id="source_0", name="source_0", kind="model", metadata={"key_0": "value_0"}),
            Source(id="source_1", name="source_1", kind="human", metadata={"key_1": "value_1"}),
            Source(id="ground_truth", name="Ground Truth", kind="ground_truth", metadata={"key_2": "value_2"}),
        ],
    }
    for i in range(num_rows):
        ## Item
        item_id = str(i)
        split = "train" if i <= num_rows / 2 else "test"
        categories = (ITEM_CATEGORIES[i % 4],)
        other_categories = [ITEM_OTHER_CATEGORIES[i % 4]]

        item = schemas["item"](
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
        tracks = []
        tracklets = []
        entities_video = []
        bboxes_video = []
        keypoints_video = []
        if has_video:
            ## Video
            num_frames = i % 2 + 1
            sequence_frames = [
                schemas["video"](
                    id=f"video_{i}_{j}",
                    category=SEQUENCE_FRAME_CATEGORY[i % 3],
                    timestamp=j / 10,
                    frame_index=j,
                    item_ref=ItemRef(id=item_id),
                    url=f"video_{i}_{j}.jpg",
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
                    item_ref=ItemRef(id=item_id),
                    view_ref=ViewRef(id=f"video_{i}_{j}", name="video"),
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

            num_tracks = i % 3
            for j in range(num_tracks):
                tracks.append(
                    schemas["tracks"](
                        id=f"track_{i}_{j}",
                        name=f"track_{i}_{j}",
                        item_ref=ItemRef(id=item_id),
                        created_at=datetime(2021, 1, 1, 0, 0, 0),
                        updated_at=datetime(2021, 1, 1, 0, 0, 0),
                    )
                )
                for k in range(num_frames):
                    tracklets.append(
                        schemas["tracklets"](
                            id=f"tracklet_{i}_{j}_{k}",
                            item_ref=ItemRef(id=item_id),
                            parent_ref=ViewRef(id=f"track_{i}_{j}", name="tracks"),
                            view_ref=ViewRef(id=f"video_{i}_{k}", name="video"),
                            start_timestep=j,
                            end_timestep=j * 4,
                            start_timestamp=j * 0.1,
                            end_timestamp=j * 4 * 0.1,
                            created_at=datetime(2021, 1, 1, 0, 0, 0),
                            updated_at=datetime(2021, 1, 1, 0, 0, 0),
                        )
                    )
                    ## Entity video
                    entities_video.append(
                        schemas["entities_video"](
                            id=f"entity_video_{i}_{j}_{k}",
                            item_ref=ItemRef(id=item_id),
                            view_ref=ViewRef(id=f"video_{i}_{k}", name="video"),
                            parent_ref=EntityRef(id=f"track_{i}_{j}", name="tracks"),
                            created_at=datetime(2021, 1, 1, 0, 0, 0),
                            updated_at=datetime(2021, 1, 1, 0, 0, 0),
                        )
                    )
                    num_bboxes_and_keypoints = i % 4
                    for m in range(num_bboxes_and_keypoints):
                        ## Bboxes video
                        bboxes_video.append(
                            schemas["bboxes_video"](
                                coords=[m, m, m * 25, m * 25],
                                format="xywh",
                                is_normalized=False,
                                confidence=0.25 * m,
                                id=f"bbox_{i}_{j}_{k}_{m}",
                                item_ref=ItemRef(id=item_id),
                                view_ref=ViewRef(id=f"video_{i}_{k}", name="video"),
                                entity_ref=EntityRef(id=f"entity_video_{i}_{j}_{k}", name="entities_video"),
                                source_ref=SourceRef(id="source_0"),
                                created_at=datetime(2021, 1, 1, 0, 0, 0),
                                updated_at=datetime(2021, 1, 1, 0, 0, 0),
                            )
                        )
                        ## Keypoints video
                        keypoints_video.append(
                            schemas["keypoints_video"](
                                template_id="template_id",
                                coords=[m, m],
                                states=["visible" if m % 2 == 0 else "invisible"],
                                id=f"keypoints_video_{i}_{j}_{k}_{m}",
                                item_ref=ItemRef(id=item_id),
                                view_ref=ViewRef(id=f"video_{i}_{k}", name="video"),
                                entity_ref=EntityRef(id=f"entity_video_{i}_{j}_{k}", name="entities_video"),
                                source_ref=SourceRef(id="source_1"),
                                created_at=datetime(2021, 1, 1, 0, 0, 0),
                                updated_at=datetime(2021, 1, 1, 0, 0, 0),
                            )
                        )

        has_image = (i % 3 > 0) or i == 0
        if has_image:
            ## Image
            image = schemas["image"](
                id=f"image_{i}",
                item_ref=ItemRef(id=item_id),
                url=f"image_{i}.jpg",
                width=100,
                height=100,
                format="jpg",
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
            )

            ## Entity image
            entity_image = schemas["entity_image"](
                id=f"entity_image_{i}",
                item_ref=ItemRef(id=item_id),
                view_ref=ViewRef(id=f"image_{i}", name="image"),
                category=ENTITY_CATEGORY[i % 4 * 2 + i % 2],
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
            )

            ## Bbox image
            bbox_image = schemas["bbox_image"](
                coords=[i, i, i * 25, i * 25],
                format="xywh",
                is_normalized=False,
                confidence=(num_rows - i) / num_rows,
                is_difficult=i % 2 == 0,
                id=f"bbox_image_{i}",
                item_ref=ItemRef(id=item_id),
                view_ref=ViewRef(id=f"image_{i}", name="image"),
                entity_ref=EntityRef(id=f"entity_image_{i}", name="entity_image"),
                source_ref=SourceRef(id=(f"source_{i % 3}") if i % 3 != 2 else "ground_truth"),
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
            )

            ## Mask image
            mask_image = schemas["mask_image"](
                id=f"mask_image_{i}",
                item_ref=ItemRef(id=item_id),
                view_ref=ViewRef(id=f"image_{i}", name="image"),
                entity_ref=EntityRef(id=f"entity_image_{i}", name="entity_image"),
                size=[10, 10],
                counts=bytes(b";37000k1"),
                source_ref=SourceRef(id=(f"source_{i % 3}") if i % 3 != 2 else "ground_truth"),
                created_at=datetime(2021, 1, 1, 0, 0, 0),
                updated_at=datetime(2021, 1, 1, 0, 0, 0),
            )

            ## Keypoints image
            num_keypoints = i % 4
            keypoints_image = []
            for j in range(num_keypoints):
                keypoints_image.append(
                    schemas["keypoints_image"](
                        template_id="template_id",
                        coords=[j, j],
                        states=["visible" if j % 2 == 0 else "invisible"],
                        id=f"keypoints_image_{i}_{j}",
                        item_ref=ItemRef(id=item_id),
                        view_ref=ViewRef(id=f"image_{i}", name="image"),
                        entity_ref=EntityRef(id=f"entity_image_{i}", name="entity_image"),
                        source_ref=SourceRef(id=(f"source_{i % 3}") if i % 3 != 2 else "ground_truth"),
                        created_at=datetime(2021, 1, 1, 0, 0, 0),
                        updated_at=datetime(2021, 1, 1, 0, 0, 0),
                    )
                )

            ## Image embedding
            image_embedding = schemas["image_embedding"](
                id=f"image_embedding_{i}",
                item_ref=ItemRef(id=item_id),
                image=image,
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
            "item": item,
            "video": sequence_frames,
            "image": image,
            "entity_image": entity_image,
            "entities_video": entities_video,
            "tracks": tracks,
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
        return generate_data_item_image_bboxes_keypoint(self.num_rows, self.item_schema_name, self.item_schema)


class DatasetBuilderVQA(DatasetBuilder):
    def __init__(self, num_rows: int = 4, *args, **kwargs):
        self.num_rows = num_rows
        super().__init__(*args, **kwargs)

    def generate_data(self):
        return generate_data_item_vqa(self.num_rows, self.item_schema_name, self.item_schema)


class DatasetBuilderMultiViewTrackingAndImage(DatasetBuilder):
    def __init__(self, num_rows: int = 5, *args, **kwargs):
        self.num_rows = num_rows
        super().__init__(*args, **kwargs)

    def generate_data(self):
        return generate_data_multi_view_tracking_and_image(self.num_rows, self.schemas)


@pytest.fixture()
def dataset_builder_image_bboxes_keypoint(
    dataset_item_image_bboxes_keypoint,
    info_dataset_image_bboxes_keypoint,
    num_rows=5,
):
    return DatasetBuilderImageBboxesKeypoint(
        num_rows,
        tempfile.mkdtemp(),
        dataset_item_image_bboxes_keypoint,
        info_dataset_image_bboxes_keypoint,
    )


@pytest.fixture()
def dataset_builder_vqa(
    dataset_item_vqa,
    info_dataset_vqa,
    num_rows=4,
):
    return DatasetBuilderVQA(
        num_rows,
        tempfile.mkdtemp(),
        dataset_item_vqa,
        info_dataset_vqa,
    )


@pytest.fixture()
def dataset_builder_multi_view_tracking_and_image(
    dataset_item_multi_view_tracking_and_image: type[DatasetItem],
    info_dataset_multi_view_tracking_and_image: DatasetInfo,
    num_rows: int = 5,
):
    return DatasetBuilderMultiViewTrackingAndImage(
        num_rows,
        tempfile.mkdtemp(),
        dataset_item_multi_view_tracking_and_image,
        info_dataset_multi_view_tracking_and_image,
    )
