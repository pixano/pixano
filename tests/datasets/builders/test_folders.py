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
from pixano.datasets.workspaces.dataset_items import DefaultImageDatasetItem
from pixano.features import Conversation, Entity, Image, Item, Message, Video
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
    def test_image_video_init(self, image_folder_builder, video_folder_builder, entity_category):
        assert isinstance(image_folder_builder, ImageFolderBuilder)
        assert isinstance(video_folder_builder, VideoFolderBuilder)
        assert image_folder_builder.source_dir.is_dir()
        assert image_folder_builder.target_dir.is_dir()
        assert video_folder_builder.source_dir.is_dir()
        assert video_folder_builder.target_dir.is_dir()
        assert image_folder_builder.views_schema == {"view": Image}
        assert video_folder_builder.views_schema == {"view": Video}
        assert image_folder_builder.entities_schema == {"entities": entity_category}
        assert video_folder_builder.entities_schema == {"entities": entity_category}

    def test_vqa_init(self, vqa_folder_builder, vqa_folder_builder_no_jsonl):
        assert isinstance(vqa_folder_builder, VQAFolderBuilder)
        assert isinstance(vqa_folder_builder_no_jsonl, VQAFolderBuilder)
        assert vqa_folder_builder.source_dir.is_dir()
        assert vqa_folder_builder.target_dir.is_dir()
        assert vqa_folder_builder_no_jsonl.source_dir.is_dir()
        assert vqa_folder_builder_no_jsonl.target_dir.is_dir()
        assert vqa_folder_builder.views_schema == {"image": Image}
        assert vqa_folder_builder_no_jsonl.views_schema == {"image": Image}
        assert vqa_folder_builder.entities_schema == {"objects": Entity, "conversations": Conversation}
        assert vqa_folder_builder_no_jsonl.entities_schema == {"objects": Entity, "conversations": Conversation}

    def test_url_prefix_init(self, dataset_item_bboxes_metadata):
        source_dir = Path(tempfile.mkdtemp())
        target_dir = Path(tempfile.mkdtemp())
        urls_relative_path = source_dir.name

        ImageFolderBuilder(
            media_dir=source_dir.parent,
            library_dir=target_dir,
            info=DatasetInfo(name="test", description="test"),
            dataset_item=dataset_item_bboxes_metadata,
            dataset_path=urls_relative_path,
        )

    def test_no_jsonl(self):
        source_dir = Path(tempfile.mkdtemp())
        target_dir = Path(tempfile.mkdtemp())
        ImageFolderBuilder(
            media_dir=source_dir.parent,
            library_dir=target_dir,
            info=DatasetInfo(name="test", description="test"),
            dataset_path=source_dir.name,
        )

    def test_error_init(self, entity_category) -> None:
        source_dir = Path(tempfile.mkdtemp())
        target_dir = Path(tempfile.mkdtemp())

        # test 1: no schema with FolderBaseBuilder
        with pytest.raises(ValueError, match="A schema is required."):
            FolderBaseBuilder(
                media_dir=source_dir.parent,
                library_dir=target_dir,
                info=DatasetInfo(name="test", description="test"),
                dataset_path=source_dir.name,
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
                media_dir=source_dir.parent,
                library_dir=target_dir,
                info=DatasetInfo(name="test", description="test"),
                dataset_path=source_dir.name,
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
                media_dir=source_dir.parent,
                library_dir=target_dir,
                info=DatasetInfo(name="test", description="test"),
                dataset_path=source_dir.name,
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
                media_dir=source_dir.parent,
                library_dir=target_dir,
                info=DatasetInfo(name="test", description="test"),
                dataset_path=source_dir.name,
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
        assert view.url == "test_dataset/train/item_0.jpg"
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
        assert view.url == "test_dataset/train/item_0.mp4"
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
        entity_name = "entities"

        # add test source id
        image_folder_builder.source_id = "source_id"

        # test 1: one bbox infered
        entities_data = {"bbox": [[0, 0, 0.2, 0.2]]}
        entities, annotations = image_folder_builder._create_objects_entities(
            item, [("view", view)], entity_name, entity_category, entities_data
        )

        assert len(entities) == 1
        assert isinstance(entities[entity_name][0], entity_category)
        assert isinstance(entities[entity_name][0].id, str) and len(entities[entity_name][0].id) == 22
        assert entities[entity_name][0].model_dump(exclude_timestamps=True) == entity_category(
            id=entities[entity_name][0].id,
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
            entity_ref=EntityRef(id=entities[entity_name][0].id, name=entity_name),
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
        entities, annotations = image_folder_builder._create_objects_entities(
            item, [("view", view)], entity_name, entity_category, entities_data
        )
        assert len(entities) == 1
        assert isinstance(entities[entity_name][0], entity_category)
        assert isinstance(entities[entity_name][0].id, str) and len(entities[entity_name][0].id) == 22
        assert entities[entity_name][0].model_dump(exclude_timestamps=True) == entity_category(
            id=entities[entity_name][0].id,
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
            entity_ref=EntityRef(id=entities[entity_name][0].id, name=entity_name),
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
        entities, annotations = image_folder_builder._create_objects_entities(
            item, [("view", view)], entity_name, entity_category, entities_data
        )
        assert len(entities[entity_name]) == 2
        assert isinstance(entities[entity_name][0], entity_category)
        assert isinstance(entities[entity_name][1], entity_category)
        assert isinstance(entities[entity_name][0].id, str) and len(entities[entity_name][0].id) == 22
        assert isinstance(entities[entity_name][1].id, str) and len(entities[entity_name][1].id) == 22
        assert entities[entity_name][0].model_dump(exclude_timestamps=True) == entity_category(
            id=entities[entity_name][0].id,
            item_ref=ItemRef(id=item.id),
            view_ref=ViewRef(id=view.id, name="view"),
            category="none",
        ).model_dump(exclude_timestamps=True)
        assert entities[entity_name][1].model_dump(exclude_timestamps=True) == entity_category(
            id=entities[entity_name][1].id,
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
            entity_ref=EntityRef(id=entities[entity_name][0].id, name=entity_name),
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
            entity_ref=EntityRef(id=entities[entity_name][1].id, name=entity_name),
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
        entities, annotations = image_folder_builder._create_objects_entities(
            item, [("view", view)], entity_name, entity_category, entities_data
        )
        assert len(entities) == 1
        assert isinstance(entities[entity_name][0], entity_category)
        assert isinstance(entities[entity_name][0].id, str) and len(entities[entity_name][0].id) == 22
        assert entities[entity_name][0].model_dump(exclude_timestamps=True) == entity_category(
            id=entities[entity_name][0].id,
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
            entity_ref=EntityRef(id=entities[entity_name][0].id, name=entity_name),
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
            entity_ref=EntityRef(id=entities[entity_name][0].id, name=entity_name),
            source_ref=SourceRef(id="source_id"),
            template_id="template_0",
            coords=[10, 10, 20, 20, 30, 30],
            states=["visible", "visible", "visible"],
        ).model_dump(exclude_timestamps=True)

        # test 5: error infer keypoints
        entities_data = {"keypoint": [[10, 10, 20, 20, 30, 30]]}
        with pytest.raises(ValueError, match="not supported for infered entity creation."):
            entities = image_folder_builder._create_objects_entities(
                item, [("view", view)], entity_name, entity_category, entities_data
            )

        # test 6: error attribute not found in entity schema
        entities_data = {"bbox": [[0, 0, 0.2, 0.2]], "unknown": [0]}
        with pytest.raises(ValueError, match="Attribute unknown not found in entity schema."):
            entities = image_folder_builder._create_objects_entities(
                item, [("view", view)], "entities", entity_category, entities_data
            )

    def reconstruct_dict_list(self, generator):
        """VQA generate data by chunks, not complete dict,
        so we rebuild a list of complete dicts, knowing that "item" key
        is always first."""
        final_list = []
        temp_dict = {}
        no_finalize_for_first_one = True
        for i, piece in enumerate(generator):
            if "item" in piece:
                if no_finalize_for_first_one:
                    no_finalize_for_first_one = False
                else:
                    # "item" appears AGAIN - finalize current dict
                    final_list.append(temp_dict.copy())
                    temp_dict.clear()
            temp_dict.update(piece)
        if temp_dict:
            final_list.append(temp_dict)
        return final_list

    def test_generate_data_egde_cases(
        self,
        edge_case_folder_builder: ImageFolderBuilder,
        vqa_folder_builder_no_jsonl: ImageFolderBuilder,
        folder_no_jsonl,
    ):
        class CustomSchema(DefaultImageDatasetItem):
            metadata_str: str
            metadata_bool: bool
            metadata_int: int
            metadata_float: float
            meatadata_list: list

        image_folder_builder_no_jsonl_custom_schema = ImageFolderBuilder(
            media_dir=folder_no_jsonl.parent,
            library_dir=tempfile.mkdtemp(),
            info=DatasetInfo(name="test", description="test"),
            dataset_item=CustomSchema,
            dataset_path=folder_no_jsonl.name,
        )

        with patch(
            "pixano.datasets.builders.folders.ImageFolderBuilder.add_source", lambda *args, **kwargs: "source_id"
        ):
            ec_items = self.reconstruct_dict_list(edge_case_folder_builder.generate_data())
            nj_items = self.reconstruct_dict_list(vqa_folder_builder_no_jsonl.generate_data())
            nj_cs_items = self.reconstruct_dict_list(image_folder_builder_no_jsonl_custom_schema.generate_data())

        # test edges cases
        for i, item in enumerate(ec_items):
            actual_item: Item = item["item"]
            if i % 2 == 0:
                view: Image = item["image"]
                assert view.item_ref == ItemRef(id=actual_item.id)
                assert view.url == f"test_dataset/{actual_item.split}/item_mosaic.jpg"
            else:
                assert "image" not in item

        # test no jsonl
        split_counts = {}
        for item in nj_items:
            actual_item: Item = item["item"]
            if actual_item.split not in split_counts:
                split_counts[actual_item.split] = 0
            sc = split_counts[actual_item.split]
            view: Image = item["image"]
            assert view.item_ref == ItemRef(id=actual_item.id)
            assert view.url == f"test_dataset/{actual_item.split}/item_{sc}.{'png' if sc % 2 else 'jpg'}"
            split_counts[actual_item.split] += 1

        # test no json with custom item fields
        for item in nj_cs_items:
            actual_item = item["item"]
            fields = list(set(actual_item.field_names()) - set(Item.field_names()))
            for field in fields:
                assert field in CustomSchema.__annotations__
                assert getattr(actual_item, field) == CustomSchema.__annotations__[field]()

    def test_generate_data(self, image_folder_builder: ImageFolderBuilder, entity_category):
        with patch(
            "pixano.datasets.builders.folders.ImageFolderBuilder.add_source", lambda *args, **kwargs: "source_id"
        ):
            items = self.reconstruct_dict_list(image_folder_builder.generate_data())
        assert len(items) == 15
        assert len([item for item in items if item["item"].split == "train"]) == 10
        assert len([item for item in items if item["item"].split == "val"]) == 5
        for item in items:
            actual_item: Item = item["item"]
            view: Image = item["view"]
            i = int(actual_item.metadata.split("_")[-1])

            assert actual_item.metadata == f"metadata_{i}"

            assert view.item_ref == ItemRef(id=actual_item.id)
            assert view.url == f"test_dataset/{actual_item.split}/item_{i}.{'png' if i % 2 else 'jpg'}"

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

    def test_generate_vqa_items(self, vqa_folder_builder: VQAFolderBuilder):
        with patch(
            "pixano.datasets.builders.folders.VQAFolderBuilder.add_source", lambda *args, **kwargs: "source_id"
        ):
            items = self.reconstruct_dict_list(vqa_folder_builder.generate_data())
        assert len(items) == 4
        assert len([item for item in items if item["item"].split == "train"]) == 2
        assert len([item for item in items if item["item"].split == "val"]) == 2
        for i, item in enumerate(items):
            actual_item: Item = item["item"]
            view: Image = item["image"]

            assert view.item_ref == ItemRef(id=actual_item.id)
            assert view.url == f"test_dataset/{actual_item.split}/item_{i % 2}.{'png' if i % 2 else 'jpg'}"

            conversations: list[Conversation] = item["conversations"]
            messages: list[Message] = item["messages"]

            if i % 2 == 0:  # 1 message (question)
                assert len(conversations) == 1
                assert len(messages) == 1
                assert conversations[0].model_dump(exclude_timestamps=True) == Conversation(
                    id=conversations[0].id,
                    item_ref=ItemRef(id=actual_item.id),
                    view_ref=ViewRef(id=view.id, name="image"),
                    kind="vqa",
                ).model_dump(exclude_timestamps=True)
                messages[0].model_dump(exclude_timestamps=True) == Message(
                    id=messages[0].id,
                    item_ref=ItemRef(id=actual_item.id),
                    view_ref=ViewRef(id=view.id, name="image"),
                    entity_ref=EntityRef(id=conversations[0].id, name="conversations"),
                    source_ref=SourceRef(id="source_id"),
                    type="QUESTION",
                    content="",
                    number=0,
                    user="import",
                ).model_dump(exclude_timestamps=True)
            else:  # 2 messages: question & answer
                assert len(conversations) == 1
                assert len(messages) == 2
                assert conversations[0].model_dump(exclude_timestamps=True) == Conversation(
                    id=conversations[0].id,
                    item_ref=ItemRef(id=actual_item.id),
                    view_ref=ViewRef(id=view.id, name="image"),
                    kind="vqa",
                ).model_dump(exclude_timestamps=True)
                messages[0].model_dump(exclude_timestamps=True) == Message(
                    id=messages[0].id,
                    item_ref=ItemRef(id=actual_item.id),
                    view_ref=ViewRef(id=view.id, name="image"),
                    entity_ref=EntityRef(id=conversations[0].id, name="conversations"),
                    source_ref=SourceRef(id="source_id"),
                    type="QUESTION",
                    content="",
                    number=0,
                    user="import",
                ).model_dump(exclude_timestamps=True)
                messages[1].model_dump(exclude_timestamps=True) == Message(
                    id=messages[0].id,
                    item_ref=ItemRef(id=actual_item.id),
                    view_ref=ViewRef(id=view.id, name="image"),
                    entity_ref=EntityRef(id=conversations[0].id, name="conversations"),
                    source_ref=SourceRef(id="source_id"),
                    type="ANSWER",
                    content="",
                    number=0,
                    user="import",
                ).model_dump(exclude_timestamps=True)
