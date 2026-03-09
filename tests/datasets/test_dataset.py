from pathlib import Path

from pixano.datasets.dataset import Dataset
from pixano.datasets.dataset_info import DatasetInfo
from pixano.schemas import PDF, Entity, Image, PointCloud, Record, SchemaGroup, SequenceFrame, View


class CustomEntity(Entity):
    category: str = ""
    is_group: bool = False


class CustomView(View):
    category: str = ""
    is_group: bool = False


def build_dataset_info(
    *,
    entity_schema: type[Entity] = Entity,
    view_schema: type[View] = View,
    extra_tables: dict[str, type[View]] | None = None,
) -> DatasetInfo:
    tables = {
        SchemaGroup.RECORD.value: Record,
        "views": view_schema,
        "entities": entity_schema,
    }
    if extra_tables is not None:
        tables.update(extra_tables)

    return DatasetInfo(
        name="unit-test-dataset",
        description="Dataset used by Dataset unit tests.",
        tables=tables,
    )


def create_dataset(
    dataset_path: Path,
    *,
    entity_schema: type[Entity] = Entity,
    view_schema: type[View] = View,
    extra_tables: dict[str, type[View]] | None = None,
) -> Dataset:
    info = build_dataset_info(entity_schema=entity_schema, view_schema=view_schema, extra_tables=extra_tables)
    return Dataset.create(dataset_path, info)


def test_create_initializes_base_tables_and_files(tmp_path: Path):
    dataset_path = tmp_path / "base-dataset"

    dataset = create_dataset(dataset_path)

    assert dataset.path == dataset_path
    assert dataset.info.id != ""
    assert (dataset_path / Dataset._INFO_FILE).is_file()
    assert (dataset_path / Dataset._FEATURES_VALUES_FILE).is_file()
    assert (dataset_path / Dataset._DB_PATH).is_dir()
    assert set(dataset.open_tables().keys()) == {"record", "views", "entities"}
    assert dataset.open_table("source").count_rows() == 0
    assert dataset.open_table("record").count_rows() == 0
    assert dataset.open_table("views").count_rows() == 0
    assert dataset.open_table("entities").count_rows() == 0
    assert dataset.num_rows == 0


def test_add_records_inserts_base_rows_in_dependency_order(tmp_path: Path):
    dataset = create_dataset(tmp_path / "base-add-records")
    assert dataset.num_rows == 0

    record = Record(id="record-1", split="train")
    parent_entity = Entity(id="entity-parent", record_id=record.id)
    child_entity = Entity(id="entity-child", record_id=record.id, parent_id=parent_entity.id)
    view = View(id="view-1", record_id=record.id, logical_name="front_camera")

    dataset.add_records(
        {
            "entities": [child_entity, parent_entity],
            "views": view,
            "record": record,
        }
    )

    stored_record = dataset.get_data("record", ids=record.id)
    stored_view = dataset.get_data("views", ids=view.id)
    stored_parent = dataset.get_data("entities", ids=parent_entity.id)
    stored_child = dataset.get_data("entities", ids=child_entity.id)

    assert stored_record is not None
    assert stored_record.id == record.id
    assert stored_record.split == "train"
    assert stored_view is not None
    assert stored_view.record_id == record.id
    assert stored_view.logical_name == "front_camera"
    assert stored_parent is not None
    assert stored_parent.record_id == record.id
    assert stored_child is not None
    assert stored_child.record_id == record.id
    assert stored_child.parent_id == parent_entity.id
    assert dataset.open_table("entities").count_rows() == 2
    assert dataset.open_table("views").count_rows() == 1
    assert dataset.num_rows == 1


def test_create_preserves_custom_component_schema_fields(tmp_path: Path):
    dataset = create_dataset(
        tmp_path / "custom-create",
        entity_schema=CustomEntity,
        view_schema=CustomView,
    )

    entity_schema = dataset.info.tables["entities"]
    view_schema = dataset.info.tables["views"]

    assert issubclass(entity_schema, Entity)
    assert issubclass(view_schema, View)
    assert {"id", "record_id", "parent_id", "category", "is_group"} <= set(entity_schema.model_fields)
    assert {"id", "record_id", "logical_name", "category", "is_group"} <= set(view_schema.model_fields)
    assert {"category", "is_group"} <= set(dataset.open_table("entities").schema.names)
    assert {"category", "is_group"} <= set(dataset.open_table("views").schema.names)


def test_add_records_persists_custom_component_fields(tmp_path: Path):
    dataset = create_dataset(
        tmp_path / "custom-add-records",
        entity_schema=CustomEntity,
        view_schema=CustomView,
    )

    record = Record(id="record-1", split="validation")
    entity = CustomEntity(
        id="entity-1",
        record_id=record.id,
        category="group",
        is_group=True,
    )
    view = CustomView(
        id="view-1",
        record_id=record.id,
        logical_name="front_camera",
        category="rgb",
        is_group=False,
    )

    dataset.add_records(
        {
            "views": view,
            "entities": entity,
            "record": record,
        }
    )

    stored_entity = dataset.get_data("entities", ids=entity.id)
    stored_view = dataset.get_data("views", ids=view.id)

    assert stored_entity is not None
    assert stored_entity.record_id == record.id
    assert stored_entity.category == "group"
    assert stored_entity.is_group is True
    assert stored_view is not None
    assert stored_view.record_id == record.id
    assert stored_view.logical_name == "front_camera"
    assert stored_view.category == "rgb"
    assert stored_view.is_group is False


def test_add_records_batch_persists_multiple_view_types(tmp_path: Path):
    dataset = create_dataset(
        tmp_path / "batch-multi-view-records",
        extra_tables={
            "image": Image,
            "text": PDF,
            "frames": SequenceFrame,
            "point_cloud": PointCloud,
        },
    )

    document_record = Record(id="record-document", split="train")
    scene_record = Record(id="record-scene", split="validation")
    image = Image(
        id="image-1",
        record_id=document_record.id,
        logical_name="document-image",
        uri="image-1.jpg",
        width=640,
        height=480,
        format="jpg",
    )
    pdf = PDF(
        id="pdf-1",
        record_id=document_record.id,
        logical_name="document-pdf",
        raw_bytes=b"%PDF-1.7 document",
        num_pages=3,
    )
    first_frame = SequenceFrame(
        id="frame-2",
        record_id=scene_record.id,
        logical_name="video",
        uri="frame-2.jpg",
        width=1920,
        height=1080,
        format="jpg",
        timestamp=0.2,
        frame_index=2,
    )
    second_frame = SequenceFrame(
        id="frame-0",
        record_id=scene_record.id,
        logical_name="video",
        uri="frame-0.jpg",
        width=1920,
        height=1080,
        format="jpg",
        timestamp=0.0,
        frame_index=0,
    )
    point_cloud = PointCloud(
        id="point-cloud-1",
        record_id=scene_record.id,
        logical_name="lidar",
        uri="point-cloud-1.pcd",
    )

    dataset.add_records(
        {
            "record": [scene_record, document_record],
            "point_cloud": point_cloud,
            "frames": [first_frame, second_frame],
            "text": pdf,
            "image": image,
        }
    )

    stored_records = dataset.get_data("record", limit=10, sortcol="id", order="asc")
    stored_image = dataset.get_data("image", ids=image.id)
    stored_pdf = dataset.get_data("text", ids=pdf.id)
    stored_frames = dataset.get_data("frames", record_ids=[scene_record.id], sortcol="frame_index", order="asc")
    stored_point_cloud = dataset.get_data("point_cloud", ids=point_cloud.id)

    assert [record.id for record in stored_records] == [document_record.id, scene_record.id]
    assert stored_image is not None
    assert stored_image.record_id == document_record.id
    assert stored_image.logical_name == "document-image"
    assert stored_pdf is not None
    assert stored_pdf.record_id == document_record.id
    assert stored_pdf.logical_name == "document-pdf"
    assert stored_pdf.num_pages == 3
    assert [frame.id for frame in stored_frames] == ["frame-0", "frame-2"]
    assert [frame.timestamp for frame in stored_frames] == [0.0, 0.2]
    assert stored_point_cloud is not None
    assert stored_point_cloud.record_id == scene_record.id
    assert stored_point_cloud.logical_name == "lidar"
    assert dataset.open_table("image").count_rows() == 1
    assert dataset.open_table("text").count_rows() == 1
    assert dataset.open_table("frames").count_rows() == 2
    assert dataset.open_table("point_cloud").count_rows() == 1
    assert dataset.num_rows == 2
