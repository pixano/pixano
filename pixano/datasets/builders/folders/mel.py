# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from collections import defaultdict
from pathlib import Path
from typing import Any, Iterator, Mapping

import pyarrow.json as pa_json
import shortuuid

from pixano.datasets.builders.folders import image
from pixano.datasets.builders.folders.base import FolderBaseBuilder
from pixano.datasets.dataset_schema import DatasetItem
from pixano.datasets.workspaces import WorkspaceType
from pixano.datasets.workspaces.dataset_items import DefaultMelDatasetItem
from pixano.features import (
    BaseSchema,
    Entity,
    Item,
    View,
    create_bbox,
    is_bbox,
)
from pixano.features.schemas.annotations import Annotation
from pixano.features.schemas.annotations.info_extraction import is_text_span
from pixano.features.schemas.registry import _PIXANO_SCHEMA_REGISTRY
from pixano.features.schemas.source import SourceKind
from pixano.features.schemas.views.image import is_image
from pixano.features.schemas.views.text import is_text
from pixano.features.types.schema_reference import EntityRef, ItemRef, SourceRef, ViewRef
from pixano.features.utils.creators import create_instance_of_schema


# Text extensions
TEXT_EXTENSIONS = [
    ".txt",
    ".md",
]

# Span extensions
SPAN_EXTENSIONS = [
    ".ann",
    ".bio",
]


class MELFolderBuilder(FolderBaseBuilder):
    """MEL (Multimodal Entity Linking) Folder Builder.

    The folder structure should be as follows:
        - source_dir/{split}/{item}.{ext}
        - source_dir/{split}/metadata.jsonl

    The metadata file should be a jsonl file with the following format:
    ```json
        [
            {
                "image": "item1.jpg",
                "text": "item1.txt",
                "metadata1": "value1",
                "metadata2": "value2",
                ...
                "objects": {
                    "text_spans": [val1, val2, ...],
                    "bboxes": [val1, val2, ...],
                    ...
                }
            },
            {
                "image": "item2.jpg",
                "text": "item2.txt",
                "metadata1": "value1",
                "metadata2": "value2",
                ...
                "objects": {
                    "text_spans": [val1, val2, ...],
                    "bboxes": [val1, val2, ...],
                    ...
                }
            },
            ...
        ]
    ```

    Note:
        Multiple views are supported. When entity data in ``metadata.jsonl`` includes a ``"view_ref"`` key
        whose value matches a view field name, that entity (and its annotations) will reference the specified
        view. Without ``"view_ref"``, the first view is used by default.
        If you give a list of images for a single view field, they will be put in a mosaic.

    Attributes:
        source_dir: The source directory for the dataset.
        view_name: The name of the view schema.
        view_schema: The schema of the view.
        entity_name: The name of the entities schema.
        entity_schema: The schema of the entities.
        METADATA_FILENAME: The metadata filename.
        EXTENSIONS: The list of supported extensions.
        WORKSPACE_TYPE: The workspace type of the dataset. Subclass should override this attribute if workspace is
            known.
    """

    METADATA_FILENAME: str = "metadata.jsonl"
    EXTENSIONS_IMAGES: list[str] = image.IMAGE_EXTENSIONS
    EXTENSIONS_TEXTS: list[str] = TEXT_EXTENSIONS
    EXTENSIONS_SPANS: list[str] = SPAN_EXTENSIONS
    WORKSPACE_TYPE = WorkspaceType.IMAGE_TEXT_ENTITY_LINKING
    DEFAULT_SCHEMA: type[DatasetItem] = DefaultMelDatasetItem

    def generate_data(
        self,
    ) -> Iterator[dict[str, BaseSchema | list[BaseSchema]]]:
        """Generate data from the source directory.

        Returns:
            An iterator over the data following the dataset schemas.
        """
        self.source_id = self.add_source("Builder", SourceKind.OTHER)
        for split in self.source_dir.glob("*"):
            if not split.is_dir() or split.name.startswith("."):
                continue

            try:
                dataset_pieces = self._read_metadata(split / self.METADATA_FILENAME)
            except FileNotFoundError:
                dataset_pieces = None

            if dataset_pieces is None:
                # Not handeled yet
                continue

            for i, dataset_piece in enumerate(dataset_pieces):
                print("\n", i, str(dataset_piece))

                item_metadata = {}
                for k in dataset_piece.keys():
                    if (
                        k not in self.views_schema
                        and k not in self.entities_schema
                        and k not in self.annotations_schema
                    ):
                        item_metadata.update({k: dataset_piece.get(k, None)})
                for k in item_metadata.keys():
                    dataset_piece.pop(k, None)

                # create item
                if "id" not in item_metadata:
                    item_metadata["id"] = f"item_{split.name}_{i}" if self.use_image_name_as_id else shortuuid.uuid()
                if "split" not in item_metadata:
                    item_metadata["split"] = split.name
                item = self._create_item(**item_metadata)
                print(f"{item=}", "dataset_piece=", dataset_piece)

                # create view
                views_data: list[tuple[str, View]] = []
                for k, v in dataset_piece.items():
                    if k in self.views_schema:
                        view_name = k
                        view_schema = self.views_schema.get(view_name)
                        if view_schema is not None:
                            view_file = self.source_dir / Path(v)
                            if not view_file.is_file():  # no split path in metadata.jsonl
                                view_file = self.source_dir / split.name / Path(v)

                            if view_file.is_file() and view_file.suffix in self.EXTENSIONS_IMAGES:
                                view = self._create_view(item, view_file, view_schema)
                                views_data.append((view_name, view))
                            elif view_file.is_file() and view_file.suffix in self.EXTENSIONS_TEXTS:
                                view = self._create_view(item, view_file, view_schema)
                                views_data.append((view_name, view))

                print("iterate on dataset_piece items")

                all_entities_data: dict[str, list[Entity]] = defaultdict(list)
                all_annotations_data: dict[str, list[Annotation]] = defaultdict(list)
                for k, v in dataset_piece.items():
                    print(k, v)
                    if k in self.entities_schema and v is not None:
                        entity_name = k
                        raw_entities_data = v
                        entity_schema = self.entities_schema.get(entity_name)
                        print("-> entity", k, entity_schema)
                        if entity_schema is not None:
                            # multimodal entity
                            entities_data, annotations_data = self._create_objects_entities(
                                item, views_data, entity_name, entity_schema, raw_entities_data
                            )

                            for name, entities in entities_data.items():
                                all_entities_data[name].extend(entities)

                            for name, annotations in annotations_data.items():
                                all_annotations_data[name].extend(annotations)

                yield {self.item_schema_name: item}
                for view_name, view in views_data:
                    yield {view_name: view}

                if all_entities_data is None:
                    continue

                yield all_entities_data
                yield all_annotations_data

    def _create_item(self, **item_metadata) -> BaseSchema:
        return self.item_schema(**item_metadata)

    def _create_view(self, item: Item, view_file: Path, view_schema: type[View]) -> View:
        if not issubclass(view_schema, View):
            raise ValueError("View schema must be a subclass of View")
        if view_schema not in _PIXANO_SCHEMA_REGISTRY.values():
            raise ValueError(
                f"View schema {view_schema} is not supported. You should implement your own _create_view method."
            )

        view = create_instance_of_schema(
            view_schema,
            id=view_file.stem if self.use_image_name_as_id else shortuuid.uuid(),
            item_ref=ItemRef(id=item.id),
            url=view_file,
            url_relative_path=self.media_dir,
        )
        return view

    def _create_objects_entities(
        self,
        item: Item,
        views_data: list[tuple[str, View]],
        entity_name: str,
        entity_schema: type[Entity],
        entities_data: dict[str, Any],
    ) -> tuple[dict[str, list[Entity]], dict[str, list[Annotation]]]:
        entities: dict[str, list[Entity]] = defaultdict(list)
        annotations: dict[str, list[Annotation]] = defaultdict(list)

        # Resolve target view: use "view_ref" if provided, otherwise fall back to first view
        view_ref_name = entities_data.pop("view_ref", None) if isinstance(entities_data, dict) else None
        if view_ref_name is not None:
            matched = [(n, v) for n, v in views_data if n == view_ref_name]
            if not matched:
                raise ValueError(f"view_ref '{view_ref_name}' not found in views: {[n for n, _ in views_data]}")
            view_name, view = matched[0]
        else:
            view_name, view = views_data[0]

        text_matched = [(n, v) for n, v in views_data if is_text(type(v))]
        image_matched = [(n, v) for n, v in views_data if is_image(type(v))]

        if not text_matched and not image_matched:
            raise ValueError(f"Could not identify neither text or image view : {[n for n, _ in views_data]}")

        text_view_name, text_view = None, None
        if text_matched:
            text_view_name, text_view = text_matched[0]
        else:
            print(f"Could not identify text view : {[n for n, _ in views_data]}")

        image_view_name, image_view = None, None
        if image_matched:
            image_view_name, image_view = image_matched[0]
        else:
            print(f"Could not identify image view : {[n for n, _ in views_data]}")

        entities_attrs = list(entities_data.keys())
        for attr in entities_attrs:
            if attr not in entity_schema.model_fields.keys() and attr not in self.schemas.keys():
                raise ValueError(f"Attribute {attr} not found in entity schema and is not a schema annotation.")

        # check if all list of entities data have same length
        nums_entities = {len(v) if isinstance(v, list) else 1 for v in entities_data.values() if v is not None}
        if len(nums_entities) > 1:
            raise ValueError("All list of entities data must have same length")
        elif len(nums_entities) == 0:
            return {}, {}

        num_entities = nums_entities.pop()
        entities_data = {k: v if isinstance(v, list) else [v] for k, v in entities_data.items() if v is not None}
        entities_attrs = list(entities_data.keys())

        for i in range(num_entities):
            entity = {}
            entity_annotations: dict[str, Any] = {}
            entity_id = shortuuid.uuid()
            for attr in entities_attrs:
                if entities_data[attr] is None:
                    continue

                print(attr, entities_data[attr])

                # check if attribute is an annotation schema, otherwise it must be a metadata
                is_attr_schema = attr in self.schemas
                if is_attr_schema and not issubclass(self.schemas[attr], Annotation):
                    raise ValueError(f"Attribute {attr} must be a subclass of Annotation")

                # create annotation if attribute is an annotation schema
                if is_attr_schema:
                    if attr not in entity_annotations:
                        entity_annotations[attr] = []

                    schema = self.schemas[attr]
                    if entities_data[attr][i] is None:
                        continue
                    if isinstance(entities_data[attr][i], Mapping):
                        if is_text_span(schema, True) and text_view is not None and text_view_name is not None:
                            annotation = create_instance_of_schema(
                                schema,
                                id=shortuuid.uuid(),
                                item_ref=ItemRef(id=item.id),
                                view_ref=ViewRef(id=text_view.id, name=text_view_name),
                                entity_ref=EntityRef(id=entity_id, name=entity_name),
                                source_ref=SourceRef(id=self.source_id),
                                **entities_data[attr][i],
                            )
                        else:
                            annotation = create_instance_of_schema(
                                schema,
                                id=shortuuid.uuid(),
                                item_ref=ItemRef(id=item.id),
                                view_ref=ViewRef(id=view.id, name=view_name),
                                entity_ref=EntityRef(id=entity_id, name=entity_name),
                                source_ref=SourceRef(id=self.source_id),
                                **entities_data[attr][i],
                            )
                    else:
                        # TODO check jsonl format for mask & keypoints
                        if is_bbox(schema, True) and image_view is not None and image_view_name is not None:
                            annotation = create_bbox(
                                id=shortuuid.uuid(),
                                item_ref=ItemRef(id=item.id),
                                view_ref=ViewRef(id=image_view.id, name=image_view_name),
                                entity_ref=EntityRef(id=entity_id, name=entity_name),
                                source_ref=SourceRef(id=self.source_id),
                                coords=entities_data[attr][i],
                                format="xywh",
                                is_normalized=all(0 <= x <= 1 for x in entities_data[attr][i]),
                                confidence=1.0,
                            )
                        else:
                            raise ValueError(f"Schema {schema} not supported for infered entity creation.")

                    print(f"New annotation {attr}=>", annotation)

                    entity_annotations[attr].append(annotation)
                else:
                    print(f"new metadata {attr}", entities_data[attr][i])

                    entity[attr] = entities_data[attr][i]
            entities[entity_name].append(
                entity_schema(
                    id=entity_id,
                    item_ref=ItemRef(id=item.id),
                    view_ref=ViewRef(id=view.id, name=view_name),
                    **entity,
                )
            )

            for key, entity_annotation in entity_annotations.items():
                annotations[key].extend(entity_annotation)
        return entities, annotations

    def _read_metadata(self, metadata_file: Path) -> list[dict]:
        if not metadata_file.exists():
            raise FileNotFoundError(f"Metadata file {metadata_file} not found")
        return pa_json.read_json(metadata_file).to_pylist()

    def _build_default_custom_metadata_item(self) -> dict[str, Any]:
        custom_item_metadata: dict[str, Any] = {}
        custom_fields = list(set(self.item_schema.field_names()) - set(Item.field_names()))
        for field in custom_fields:
            field_type = self.item_schema.__annotations__[field]
            custom_item_metadata[field] = field_type()
        return custom_item_metadata
