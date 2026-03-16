# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import tempfile
from pathlib import Path

import pytest

from pixano.datasets import Dataset
from pixano.datasets.builders.dataset_builder import DatasetBuilder
from pixano.datasets.builders.folders import (
    FolderBaseBuilder,
    ImageFolderBuilder,
    VideoFolderBuilder,
    VQAFolderBuilder,
)
from pixano.datasets.dataset_info import DatasetInfo
from pixano.datasets.workspaces import WorkspaceType
from pixano.features import BBox, Entity, Image, Message, Record, SequenceFrame, Video
from pixano.schemas.annotations.keypoints import KeyPoints
from tests.assets.sample_data.metadata import SAMPLE_DATA_PATHS


VIDEO_INSTALLED = False
try:
    import ffmpeg

    ffmpeg.probe(SAMPLE_DATA_PATHS["video_mp4"])
    VIDEO_INSTALLED = True
except:  # noqa: E722
    pass


class TestFolderBaseBuilder:
    def test_preflight_metadata_reports_aliases_in_default_mode(self, entity_category):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_dir = Path(tmp_dir) / "test_dataset"
            split_dir = source_dir / "train"
            split_dir.mkdir(parents=True, exist_ok=True)
            (split_dir / "item_0.jpg").write_bytes(SAMPLE_DATA_PATHS["image_jpg"].read_bytes())
            (split_dir / "metadata.jsonl").write_text(
                '{"image":"item_0.jpg","objects":{"category":["person"]},"bbox":{"coords":[[0,0,10,10]],"format":["xywh"],"is_normalized":[false],"entity_index":[0]}}\n',
                encoding="utf-8",
            )

            builder = ImageFolderBuilder(
                source_dir=source_dir,
                library_dir=Path(tmp_dir) / "library",
                info=DatasetInfo(
                    name="alias_entities",
                    description="",
                    record=Record,
                    entity=entity_category,
                    bbox=BBox,
                    views={"image": Image},
                ),
            )
            report = builder.preflight_metadata()

            assert report.error_count == 0
            assert "objects -> entities" in report.aliases
            assert "bbox -> bboxes" in report.aliases

    def test_preflight_metadata_rejects_aliases_in_strict_mode(self, entity_category):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_dir = Path(tmp_dir) / "test_dataset"
            split_dir = source_dir / "train"
            split_dir.mkdir(parents=True, exist_ok=True)
            (split_dir / "item_0.jpg").write_bytes(SAMPLE_DATA_PATHS["image_jpg"].read_bytes())
            (split_dir / "metadata.jsonl").write_text(
                '{"image":"item_0.jpg","objects":{"category":["person"]}}\n',
                encoding="utf-8",
            )

            builder = ImageFolderBuilder(
                source_dir=source_dir,
                library_dir=Path(tmp_dir) / "library",
                info=DatasetInfo(
                    name="alias_entities",
                    description="",
                    record=Record,
                    entity=entity_category,
                    views={"image": Image},
                ),
                metadata_validation_mode="strict",
            )
            report = builder.preflight_metadata()

            assert report.error_count > 0
            assert "aliased_metadata_key" in report.errors

    def test_preflight_metadata_reports_missing_view_media(self, entity_category):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_dir = Path(tmp_dir) / "test_dataset"
            split_dir = source_dir / "train"
            split_dir.mkdir(parents=True, exist_ok=True)
            (split_dir / "metadata.jsonl").write_text('{"image":"missing.jpg","entities":{}}\n', encoding="utf-8")

            builder = ImageFolderBuilder(
                source_dir=source_dir,
                library_dir=Path(tmp_dir) / "library",
                info=DatasetInfo(
                    name="missing_media",
                    description="",
                    record=Record,
                    entity=entity_category,
                    views={"image": Image},
                ),
            )
            report = builder.preflight_metadata()

            assert "missing_view_media" in report.errors

    def test_generate_data_maps_objects_to_entities_alias(self, entity_category):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_dir = Path(tmp_dir) / "test_dataset"
            split_dir = source_dir / "train"
            split_dir.mkdir(parents=True, exist_ok=True)
            (split_dir / "item_0.jpg").write_bytes(SAMPLE_DATA_PATHS["image_jpg"].read_bytes())
            (split_dir / "metadata.jsonl").write_text(
                '{"image":"item_0.jpg","objects":{"category":["person"]}}\n',
                encoding="utf-8",
            )

            builder = ImageFolderBuilder(
                source_dir=source_dir,
                library_dir=Path(tmp_dir) / "library",
                info=DatasetInfo(
                    name="alias_entities",
                    description="",
                    record=Record,
                    entity=entity_category,
                    views={"image": Image},
                ),
            )
            dataset = builder.build(mode="create", check_integrity="none")

            assert dataset.open_table("entities").count_rows() == 1

    def test_generate_data_maps_image_to_sequence_frame_alias(self, entity_category):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_dir = Path(tmp_dir) / "test_dataset"
            split_dir = source_dir / "train"
            split_dir.mkdir(parents=True, exist_ok=True)
            (split_dir / "item_0.jpg").write_bytes(SAMPLE_DATA_PATHS["image_jpg"].read_bytes())
            (split_dir / "metadata.jsonl").write_text('{"image":"item_0.jpg"}\n', encoding="utf-8")

            builder = VideoFolderBuilder(
                source_dir=source_dir,
                library_dir=Path(tmp_dir) / "library",
                info=DatasetInfo(
                    name="alias_views",
                    description="",
                    record=Record,
                    entity=entity_category,
                    views={"image": SequenceFrame},
                ),
            )
            dataset = builder.build(mode="create", check_integrity="none")

            assert dataset.open_table("sequence_frames").count_rows() == 1

    def test_builder_rejects_mixed_image_and_sframe_same_logical_name(self):
        class MixedViewBuilder(DatasetBuilder):
            def __init__(self, target_dir: Path):
                super().__init__(
                    target_dir=target_dir,
                    info=DatasetInfo(
                        id="mixed_views",
                        name="mixed_views",
                        description="",
                        workspace=WorkspaceType.VIDEO,
                        record=Record,
                        views={"camera_image": Image, "camera_frame": SequenceFrame},
                    ),
                )

            def generate_data(self):
                record = Record(id="record_0", split="train")
                yield {"records": record}
                yield {
                    "images": [
                        Image(
                            id="image_0",
                            record_id=record.id,
                            logical_name="camera",
                            uri="image_0.jpg",
                            width=64,
                            height=64,
                            format="jpg",
                        )
                    ]
                }
                yield {
                    "sequence_frames": [
                        SequenceFrame(
                            id="sframe_0",
                            record_id=record.id,
                            logical_name="camera",
                            uri="frame_0.jpg",
                            width=64,
                            height=64,
                            format="jpg",
                            timestamp=0.0,
                            frame_index=0,
                        )
                    ]
                }

        with tempfile.TemporaryDirectory() as tmp_dir:
            builder = MixedViewBuilder(Path(tmp_dir) / "mixed_views")

            with pytest.raises(ValueError, match="logical view family collision"):
                builder.build(mode="create", check_integrity="none", flush_every_n_samples=1)

    def test_image_video_init(self, image_folder_builder, video_folder_builder, entity_category):
        assert isinstance(image_folder_builder, ImageFolderBuilder)
        assert isinstance(video_folder_builder, VideoFolderBuilder)
        assert image_folder_builder.source_dir.is_dir()
        assert video_folder_builder.source_dir.is_dir()
        assert image_folder_builder.views_schema == {"view": Image}
        assert video_folder_builder.views_schema == {"view": SequenceFrame}
        assert image_folder_builder.entities_schema == {"entities": entity_category}
        assert video_folder_builder.entities_schema == {"entities": entity_category}

    def test_vqa_init(self, vqa_folder_builder, vqa_folder_builder_no_jsonl):
        assert isinstance(vqa_folder_builder, VQAFolderBuilder)
        assert isinstance(vqa_folder_builder_no_jsonl, VQAFolderBuilder)
        assert vqa_folder_builder.source_dir.is_dir()
        assert vqa_folder_builder_no_jsonl.source_dir.is_dir()
        assert vqa_folder_builder.views_schema == {"image": Image}
        assert vqa_folder_builder_no_jsonl.views_schema == {"image": Image}
        assert vqa_folder_builder.entities_schema == {"entities": Entity}
        assert vqa_folder_builder_no_jsonl.entities_schema == {"entities": Entity}

    def test_url_prefix_init(self):
        source_dir = Path(tempfile.mkdtemp())
        target_dir = Path(tempfile.mkdtemp())

        class RecordBBoxesMetadata(Record):
            categories: tuple[str, ...] = ()
            other_categories: list[int] = []
            name: str = ""
            index: int = 0

        ImageFolderBuilder(
            source_dir=source_dir,
            library_dir=target_dir,
            info=DatasetInfo(
                name="test",
                description="test",
                record=RecordBBoxesMetadata,
                entity=Entity,
                bbox=BBox,
                views={"image": Image},
            ),
        )

    def test_no_jsonl(self):
        source_dir = Path(tempfile.mkdtemp())
        target_dir = Path(tempfile.mkdtemp())
        ImageFolderBuilder(
            source_dir=source_dir,
            library_dir=target_dir,
            info=DatasetInfo(name="test", description="test"),
        )

    def test_error_init(self, entity_category) -> None:
        source_dir = Path(tempfile.mkdtemp())
        target_dir = Path(tempfile.mkdtemp())

        # test 1: no schemas with FolderBaseBuilder
        with pytest.raises(ValueError, match="DatasetInfo must define at least one record schema and one view"):
            FolderBaseBuilder(
                source_dir=source_dir,
                library_dir=target_dir,
                info=DatasetInfo(name="test", description="test"),
            )

        # test 2 / 3: ImageFolderBuilder defaults now provide views/entities
        builder = ImageFolderBuilder(
            source_dir=source_dir,
            library_dir=target_dir,
            info=DatasetInfo(name="test", description="test", record=Record, bbox=BBox),
        )
        assert builder.views_schema == {"image": Image}
        assert builder.entities_schema == {"entities": Entity}

        with pytest.raises(ValueError, match="incompatible with ImageFolderBuilder"):
            ImageFolderBuilder(
                source_dir=source_dir,
                library_dir=target_dir,
                info=DatasetInfo(name="test", description="test", workspace=WorkspaceType.VIDEO, record=Record),
            )

        # test 4: DatasetInfo with two views should work (multi-view support)
        builder = ImageFolderBuilder(
            source_dir=source_dir,
            library_dir=target_dir,
            info=DatasetInfo(
                name="test",
                description="test",
                record=Record,
                entity=entity_category,
                bbox=BBox,
                views={"view": Image, "view2": Image},
            ),
        )
        assert builder.views_schema == {"view": Image, "view2": Image}

        # test 5: invalid source_dir
        with pytest.raises(ValueError, match="Source directory does not exist"):
            ImageFolderBuilder(
                source_dir=source_dir / "nonexistent",
                library_dir=target_dir,
                info=DatasetInfo(name="test", description="test"),
            )

    def test_create_record(self, image_folder_builder: ImageFolderBuilder):
        record = image_folder_builder._create_record(
            id="id0",
            split="train",
            metadata="metadata",
        )
        assert isinstance(record, Record)
        assert record.split == "train"
        assert record.metadata == "metadata"

    def test_create_image_view(self, image_folder_builder: ImageFolderBuilder):
        record = image_folder_builder._create_record(
            id="id0",
            split="train",
            metadata="metadata",
        )
        view = image_folder_builder._create_view(
            record, image_folder_builder.source_dir / "train" / "item_0.jpg", "view", Image
        )

        assert isinstance(view, Image)
        assert view.record_id == record.id
        assert isinstance(view.id, str) and len(view.id) == 22
        assert view.width == 586
        assert view.height == 640
        assert view.format == "JPEG"

    @pytest.mark.skipif(not VIDEO_INSTALLED, reason="To load video files metadata, install ffmpeg")
    def test_create_video_view(self, video_folder_builder: VideoFolderBuilder):
        record = video_folder_builder._create_record(
            id="id0",
            split="train",
            metadata="metadata",
        )
        view = video_folder_builder._create_view(
            record, video_folder_builder.source_dir / "train" / "item_0.mp4", "view", Video
        )

        assert isinstance(view, Video)
        assert isinstance(view.id, str) and len(view.id) == 22
        assert view.record_id == record.id
        assert view.num_frames == 209
        assert round(view.fps, 2) == 29.97
        assert view.width == 320
        assert view.height == 240
        assert view.format == "mp4"
        assert round(view.duration, 2) == 6.97

    def test_create_entities(self, image_folder_builder: ImageFolderBuilder, entity_category):
        record = image_folder_builder._create_record(
            id="id0",
            split="train",
            metadata="metadata",
        )
        view = image_folder_builder._create_view(
            record, image_folder_builder.source_dir / "train" / "item_0.jpg", "view", Image
        )
        entity_name = "entities"

        # set test source type/name
        image_folder_builder._default_source_type = "model"
        image_folder_builder._default_source_name = "source_id"

        # test 1: one bbox infered
        entities_data = {"bbox": [[0, 0, 0.2, 0.2]]}
        entities, annotations = image_folder_builder._create_objects_entities(
            record, [("view", view)], entity_name, entity_category, entities_data
        )

        assert len(entities) == 1
        assert isinstance(entities[entity_name][0], entity_category)
        assert isinstance(entities[entity_name][0].id, str) and len(entities[entity_name][0].id) == 22
        assert entities[entity_name][0].model_dump(exclude={"created_at", "updated_at"}) == entity_category(
            id=entities[entity_name][0].id,
            record_id=record.id,
            category="none",
        ).model_dump(exclude={"created_at", "updated_at"})

        assert set(annotations.keys()) == {"bboxes"}
        assert len(annotations["bboxes"]) == 1
        assert annotations["bboxes"][0].model_dump(exclude={"created_at", "updated_at"}) == BBox(
            id=annotations["bboxes"][0].id,
            record_id=record.id,
            view_id=view.id,
            entity_id=entities[entity_name][0].id,
            source_type="model",
            source_name="source_id",
            frame_id=view.id,
            coords=[0, 0, 0.2, 0.2],
            format="xywh",
            is_normalized=True,
            confidence=1.0,
        ).model_dump(exclude={"created_at", "updated_at"})

        # test 2: one bbox not infered
        entities_data = {
            "bbox": {"coords": [0, 0, 100, 100], "format": "xyxy", "is_normalized": False, "confidence": 0.9}
        }
        entities, annotations = image_folder_builder._create_objects_entities(
            record, [("view", view)], entity_name, entity_category, entities_data
        )
        assert len(entities) == 1
        assert isinstance(entities[entity_name][0], entity_category)
        assert isinstance(entities[entity_name][0].id, str) and len(entities[entity_name][0].id) == 22
        assert entities[entity_name][0].model_dump(exclude={"created_at", "updated_at"}) == entity_category(
            id=entities[entity_name][0].id,
            record_id=record.id,
            category="none",
        ).model_dump(exclude={"created_at", "updated_at"})
        assert set(annotations.keys()) == {"bboxes"}
        assert len(annotations["bboxes"]) == 1
        assert annotations["bboxes"][0].model_dump(exclude={"created_at", "updated_at"}) == BBox(
            id=annotations["bboxes"][0].id,
            record_id=record.id,
            view_id=view.id,
            entity_id=entities[entity_name][0].id,
            source_type="model",
            source_name="source_id",
            frame_id=view.id,
            coords=[0, 0, 100, 100],
            format="xyxy",
            is_normalized=False,
            confidence=0.9,
        ).model_dump(exclude={"created_at", "updated_at"})

        # test 3: two bboxes, one infered, one not infered
        entities_data = {
            "bbox": [
                {"coords": [0, 0, 100, 100], "format": "xyxy", "is_normalized": False, "confidence": 0.5},
                [0.1, 0.1, 0.2, 0.2],
            ]
        }
        entities, annotations = image_folder_builder._create_objects_entities(
            record, [("view", view)], entity_name, entity_category, entities_data
        )
        assert len(entities[entity_name]) == 2
        assert isinstance(entities[entity_name][0], entity_category)
        assert isinstance(entities[entity_name][1], entity_category)
        assert isinstance(entities[entity_name][0].id, str) and len(entities[entity_name][0].id) == 22
        assert isinstance(entities[entity_name][1].id, str) and len(entities[entity_name][1].id) == 22
        assert entities[entity_name][0].model_dump(exclude={"created_at", "updated_at"}) == entity_category(
            id=entities[entity_name][0].id,
            record_id=record.id,
            category="none",
        ).model_dump(exclude={"created_at", "updated_at"})
        assert entities[entity_name][1].model_dump(exclude={"created_at", "updated_at"}) == entity_category(
            id=entities[entity_name][1].id,
            record_id=record.id,
            category="none",
        ).model_dump(exclude={"created_at", "updated_at"})
        assert set(annotations.keys()) == {"bboxes"}
        assert len(annotations["bboxes"]) == 2
        assert annotations["bboxes"][0].model_dump(exclude={"created_at", "updated_at"}) == BBox(
            id=annotations["bboxes"][0].id,
            record_id=record.id,
            view_id=view.id,
            entity_id=entities[entity_name][0].id,
            source_type="model",
            source_name="source_id",
            frame_id=view.id,
            coords=[0, 0, 100, 100],
            format="xyxy",
            is_normalized=False,
            confidence=0.5,
        ).model_dump(exclude={"created_at", "updated_at"})
        assert annotations["bboxes"][1].model_dump(exclude={"created_at", "updated_at"}) == BBox(
            id=annotations["bboxes"][1].id,
            record_id=record.id,
            view_id=view.id,
            entity_id=entities[entity_name][1].id,
            source_type="model",
            source_name="source_id",
            frame_id=view.id,
            coords=[0.1, 0.1, 0.2, 0.2],
            format="xywh",
            is_normalized=True,
            confidence=1.0,
        ).model_dump(exclude={"created_at", "updated_at"})

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
            record, [("view", view)], entity_name, entity_category, entities_data
        )
        assert len(entities) == 1
        assert isinstance(entities[entity_name][0], entity_category)
        assert isinstance(entities[entity_name][0].id, str) and len(entities[entity_name][0].id) == 22
        assert entities[entity_name][0].model_dump(exclude={"created_at", "updated_at"}) == entity_category(
            id=entities[entity_name][0].id,
            record_id=record.id,
            category="person",
        ).model_dump(exclude={"created_at", "updated_at"})
        assert set(annotations.keys()) == {"bboxes", "keypoints"}
        assert len(annotations["bboxes"]) == 1
        assert len(annotations["keypoints"]) == 1
        assert annotations["bboxes"][0].model_dump(exclude={"created_at", "updated_at"}) == BBox(
            id=annotations["bboxes"][0].id,
            record_id=record.id,
            view_id=view.id,
            entity_id=entities[entity_name][0].id,
            source_type="model",
            source_name="source_id",
            frame_id=view.id,
            coords=[0, 0, 0.2, 0.2],
            format="xywh",
            is_normalized=True,
            confidence=1.0,
        ).model_dump(exclude={"created_at", "updated_at"})
        assert annotations["keypoints"][0].model_dump(exclude={"created_at", "updated_at"}) == KeyPoints(
            id=annotations["keypoints"][0].id,
            record_id=record.id,
            view_id=view.id,
            entity_id=entities[entity_name][0].id,
            source_type="model",
            source_name="source_id",
            frame_id=view.id,
            template_id="template_0",
            coords=[10, 10, 20, 20, 30, 30],
            states=["visible", "visible", "visible"],
        ).model_dump(exclude={"created_at", "updated_at"})

        # test 5: error infer keypoints
        entities_data = {"keypoint": [[10, 10, 20, 20, 30, 30]]}
        with pytest.raises(ValueError, match="not supported for infered entity creation."):
            entities = image_folder_builder._create_objects_entities(
                record, [("view", view)], entity_name, entity_category, entities_data
            )

        # test 6: error attribute not found in entity schema
        entities_data = {"bbox": [[0, 0, 0.2, 0.2]], "unknown": [0]}
        with pytest.raises(ValueError, match="Attribute unknown not found in entity schema"):
            entities = image_folder_builder._create_objects_entities(
                record, [("view", view)], "entities", entity_category, entities_data
            )

    def reconstruct_dict_list(self, generator):
        """VQA generate data by chunks, not complete dict,
        so we rebuild a list of complete dicts, knowing that "records" key
        is always first."""
        final_list = []
        temp_dict = {}
        no_finalize_for_first_one = True
        for i, piece in enumerate(generator):
            if "records" in piece:
                if no_finalize_for_first_one:
                    no_finalize_for_first_one = False
                else:
                    # "records" appears AGAIN - finalize current dict
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
        class CustomRecord(Record):
            metadata_str: str = ""
            metadata_bool: bool = False
            metadata_int: int = 0
            metadata_float: float = 0.0
            meatadata_list: list = []

        image_folder_builder_no_jsonl_custom_schema = ImageFolderBuilder(
            source_dir=folder_no_jsonl,
            library_dir=tempfile.mkdtemp(),
            info=DatasetInfo(
                name="test",
                description="test",
                record=CustomRecord,
                entity=Entity,
                bbox=BBox,
                keypoint=KeyPoints,
                views={"image": Image},
            ),
        )

        ec_items = self.reconstruct_dict_list(edge_case_folder_builder.generate_data())
        nj_items = self.reconstruct_dict_list(vqa_folder_builder_no_jsonl.generate_data())
        nj_cs_items = self.reconstruct_dict_list(image_folder_builder_no_jsonl_custom_schema.generate_data())

        # test edges cases
        for i, item in enumerate(ec_items):
            actual_record: Record = item["records"]
            if i % 2 == 0:
                view: Image = item["images"]
                assert view.record_id == actual_record.id
            else:
                assert "images" not in item

        # test no jsonl
        split_counts = {}
        for item in nj_items:
            actual_record: Record = item["records"]
            if actual_record.split not in split_counts:
                split_counts[actual_record.split] = 0
            view: Image = item["images"]
            assert view.record_id == actual_record.id
            split_counts[actual_record.split] += 1

        # test no json with custom record fields
        for item in nj_cs_items:
            actual_record = item["records"]
            custom_fields = set(type(actual_record).model_fields.keys()) - set(Record.model_fields.keys())
            for field in custom_fields:
                assert field in CustomRecord.__annotations__
                assert getattr(actual_record, field) == CustomRecord.__annotations__[field]()

    def test_generate_data(self, image_folder_builder: ImageFolderBuilder, entity_category):
        items = self.reconstruct_dict_list(image_folder_builder.generate_data())
        assert len(items) == 15
        assert len([item for item in items if item["records"].split == "train"]) == 10
        assert len([item for item in items if item["records"].split == "val"]) == 5
        for item in items:
            actual_record: Record = item["records"]
            view: Image = item["images"]
            i = int(actual_record.metadata.split("_")[-1])

            assert actual_record.metadata == f"metadata_{i}"

            assert view.record_id == actual_record.id

            if i % 2:  # has entities
                entities: list[entity_category] = item["entities"]
                bboxes: list[BBox] = item["bboxes"]
                assert len(entities) == i
                for entity, bbox in zip(entities, bboxes, strict=True):
                    assert entity.model_dump(exclude={"created_at", "updated_at"}) == entity_category(
                        id=entity.id,
                        record_id=actual_record.id,
                        category="person" if i % 4 == 0 else "cat",
                    ).model_dump(exclude={"created_at", "updated_at"})
            else:  # no entities
                assert "entities" not in item
                assert "bboxes" not in item

    def test_generate_vqa_items(self, vqa_folder_builder: VQAFolderBuilder):
        items = self.reconstruct_dict_list(vqa_folder_builder.generate_data())
        assert len(items) == 4
        assert len([item for item in items if item["records"].split == "train"]) == 2
        assert len([item for item in items if item["records"].split == "val"]) == 2
        for i, item in enumerate(items):
            actual_record: Record = item["records"]
            view: Image = item["images"]

            assert view.record_id == actual_record.id

            messages: list[Message] = item["messages"]

            if i % 2 == 0:  # 1 message (question)
                assert len(messages) == 1
                assert messages[0].record_id == actual_record.id
                assert messages[0].view_id == view.id
                assert messages[0].source_type == "other"
                assert messages[0].source_name == "Builder"
                assert messages[0].type == "QUESTION"
                assert messages[0].content == "What is the greatest number ? <image 1>"
                assert messages[0].number == 0
                assert messages[0].user == "import"
                assert messages[0].choices == ["0", "15", "3.14", "58"]
            else:  # 2 messages: question & answer
                assert len(messages) == 2
                assert messages[0].conversation_id == messages[1].conversation_id
                assert messages[0].record_id == actual_record.id
                assert messages[0].type == "QUESTION"
                assert messages[0].content == "What is the greatest number ? <image 1>"
                assert messages[0].number == 0
                assert messages[0].user == "import"
                assert messages[0].choices == ["0", "15", "3.14", "58"]
                assert messages[1].record_id == actual_record.id
                assert messages[1].type == "ANSWER"
                assert messages[1].content == "58"
                assert messages[1].number == 1
                assert messages[1].user == "import"
