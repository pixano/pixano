# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path
from typing import Any, Iterator, Mapping

import pyarrow.json as pa_json
import shortuuid

from pixano.datasets.dataset_info import DatasetInfo
from pixano.datasets.dataset_schema import DatasetItem
from pixano.datasets.workspaces import WorkspaceType
from pixano.features import BaseSchema, Entity, Item, View, create_bbox, is_annotation, is_bbox, is_entity, is_view
from pixano.features.schemas.annotations.annotation import Annotation
from pixano.features.schemas.registry import _PIXANO_SCHEMA_REGISTRY
from pixano.features.schemas.source import SourceKind
from pixano.features.types.schema_reference import EntityRef, ItemRef, SourceRef, ViewRef
from pixano.features.utils.creators import create_instance_of_schema

from ..dataset_builder import DatasetBuilder


class FolderBaseBuilder(DatasetBuilder):
    """This is a class for building datasets based on a folder structure.

    The folder structure should be as follows:
        - source_dir/{split}/{item}.{ext}
        - source_dir/{split}/metadata.jsonl

    The metadata file should be a jsonl file with the following format:
    ```json
        [
            {
                "item": "item1",
                "metadata1": "value1",
                "metadata2": "value2",
                ...
                "entities": {
                    "attr1": [val1, val2, ...],
                    "attr2": [val1, val2, ...],
                    ...
                }
            },
            {
                "item": "item2",
                "metadata1": "value1",
                "metadata2": "value2",
                ...
                "entities": {
                    "attr1": [val1, val2, ...],
                    "attr2": [val1, val2, ...],
                    ...
                }
            },
            ...
        ]
    ```

    Note:
        Only one view and one entity are supported in folder builders.

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
    EXTENSIONS: list[str]
    WORKSPACE_TYPE = WorkspaceType.UNDEFINED
    DEFAULT_SCHEMA: type[DatasetItem] | None = None

    def __init__(
        self,
        source_dir: Path | str,
        target_dir: Path | str,
        info: DatasetInfo,
        dataset_item: type[DatasetItem] | None = None,
        url_prefix: Path | str | None = None,
    ) -> None:
        """Initialize the `FolderBaseBuilder`.

        Args:
            source_dir: The source directory for the dataset.
            target_dir: The target directory for the dataset.
            dataset_item: The dataset item schema.
            info: User informations (name, description, ...) for the dataset.
            url_prefix: The path to build relative URLs for the views. Useful to build dataset libraries to pass the
                relative path from the media directory.
        """
        info.workspace = self.WORKSPACE_TYPE
        if self.DEFAULT_SCHEMA is not None and dataset_item is None:
            dataset_item = self.DEFAULT_SCHEMA
        if dataset_item is None:
            raise ValueError("A schema is required.")
        super().__init__(target_dir=target_dir, dataset_item=dataset_item, info=info)
        self.source_dir = Path(source_dir)
        if url_prefix is None:
            url_prefix = Path(".")
        else:
            url_prefix = Path(url_prefix)
        self.url_prefix = url_prefix

        self.views_schema: dict[str, type[View]] = {}
        self.entities_schema: dict[str, type[Entity]] = {}
        self.annotations_schema: dict[str, type[Annotation]] = {}

        for k, s in self.schemas.items():
            if is_view(s):
                self.views_schema.update({k: s})
            elif is_entity(s):
                self.entities_schema.update({k: s})
            elif is_annotation(s):
                self.annotations_schema.update({k: s})
        if not self.views_schema or not self.entities_schema:
            raise ValueError("At least one View and one Entity schema must be defined in the schemas argument.")

        # for compatibility with actual ImageFolderBuilder that allows only one view and one entity
        # TODO - allow multiview and multi entities in base FolderBuilder
        # Note: technically VQA also allow only one view, so for now we keep the ValueError
        if len(self.views_schema) == 1:
            self.view_name, self.view_schema = list(self.views_schema.items())[0]
        else:
            raise ValueError("Only one view schema is supported in folder based builders.")
        if len(self.entities_schema) == 1:
            self.entity_name, self.entity_schema = list(self.entities_schema.items())[0]

    def generate_data(
        self,
    ) -> Iterator[dict[str, BaseSchema | list[BaseSchema]]]:
        """Generate data from the source directory.

        Returns:
            An iterator over the data following the dataset schemas.
        """
        source_id = None
        for split in self.source_dir.glob("*"):
            if split.is_dir() and not split.name.startswith("."):
                try:
                    metadata = self._read_metadata(split / self.METADATA_FILENAME)
                except FileNotFoundError:
                    metadata = None
                if metadata is None:
                    for view_file in split.glob("*"):
                        # only consider {split}/{item}.{ext} files
                        if not view_file.is_file() or view_file.suffix not in self.EXTENSIONS:
                            continue
                        # create item
                        item = self._create_item(split.name, **{})
                        # create view
                        view = self._create_view(item, view_file, self.view_schema)
                        yield {
                            self.item_schema_name: item,
                            self.view_name: view,
                        }
                else:  # metadata not None
                    # retrieve item metadata in metadata file
                    for item_metadata in metadata:
                        # extract entity metadata from item metadata
                        entities_data = item_metadata.pop(self.entity_name, None)

                        # create item
                        item = self._create_item(split.name, **item_metadata)

                        # create view
                        view_file = split / item_metadata[self.view_name]
                        view = self._create_view(item, view_file, self.view_schema)

                        if entities_data is None:
                            yield {
                                self.item_schema_name: item,
                                self.view_name: view,
                            }
                            continue
                        elif source_id is None:
                            source_id = self.add_source("Builder", SourceKind.OTHER)

                        # create entities and their annotations
                        entities, annotations = self._create_entities(item, view, entities_data, source_id)

                        yield {
                            self.item_schema_name: item,
                            self.view_name: view,
                            self.entity_name: entities,
                            **annotations,
                        }

    def _create_item(self, split: str, **item_metadata) -> BaseSchema:
        if "id" not in item_metadata:
            item_metadata["id"] = shortuuid.uuid()
        return self.item_schema(
            split=split,
            **item_metadata,
        )

    def _create_view(self, item: Item, view_file: Path, view_schema: type[View]) -> View:
        if not issubclass(view_schema, View):
            raise ValueError("View schema must be a subclass of View")
        if view_schema not in _PIXANO_SCHEMA_REGISTRY.values():
            raise ValueError(
                f"View schema {view_schema} is not supported. You should implement your own _create_view method."
            )

        view = create_instance_of_schema(
            view_schema,
            id=shortuuid.uuid(),
            item_ref=ItemRef(id=item.id),
            url=view_file,
            url_relative_path=self.source_dir,
        )
        view.url = str(self.url_prefix / view.url)
        return view

    def _create_entities(
        self, item: Item, view: View, entities_data: dict[str, Any], source_id: str
    ) -> tuple[list[Entity], dict[str, list[Annotation]]]:
        entities: list[Entity] = []
        annotations: dict[str, list[Annotation]] = {}

        entities_attrs = list(entities_data.keys())
        for attr in entities_attrs:
            if attr not in self.entity_schema.model_fields.keys() and attr not in self.schemas.keys():
                raise ValueError(f"Attribute {attr} not found in entity schema and is not a schema annotation.")

        # check if all list of entities data have same length
        nums_entities = {len(v) if isinstance(v, list) else 1 for v in entities_data.values() if v is not None}
        if len(nums_entities) > 1:
            raise ValueError("All list of entities data must have same length")
        elif len(nums_entities) == 0:
            return [], {}

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

                # check if attribute is an annotation schema
                is_attr_schema = attr in self.schemas
                if is_attr_schema and not issubclass(self.schemas[attr], Annotation):
                    raise ValueError(f"Attribute {attr} must be a subclass of Annotation")

                # create annotation if attribute is an annotation schema
                if is_attr_schema:
                    if attr not in entity_annotations:
                        entity_annotations[attr] = []

                    schema = self.schemas[attr]
                    if isinstance(entities_data[attr][i], Mapping):
                        annotation = create_instance_of_schema(
                            schema,
                            id=shortuuid.uuid(),
                            item_ref=ItemRef(id=item.id),
                            view_ref=ViewRef(id=view.id, name=self.view_name),
                            entity_ref=EntityRef(id=entity_id, name=self.entity_name),
                            source_ref=SourceRef(id=source_id),
                            **entities_data[attr][i],
                        )
                    else:
                        # TODO check jsonl format for mask & keypoints
                        if is_bbox(schema, True):
                            annotation = create_bbox(
                                id=shortuuid.uuid(),
                                item_ref=ItemRef(id=item.id),
                                view_ref=ViewRef(id=view.id, name=self.view_name),
                                entity_ref=EntityRef(id=entity_id, name=self.entity_name),
                                source_ref=SourceRef(id=source_id),
                                coords=entities_data[attr][i],
                                format="xywh",
                                is_normalized=True,
                                confidence=1.0,
                            )
                        else:
                            raise ValueError(f"Schema {schema} not supported for infered entity creation.")
                    entity_annotations[attr].append(annotation)
                else:
                    entity[attr] = entities_data[attr][i]
            entities.append(
                self.entity_schema(
                    id=entity_id,
                    item_ref=ItemRef(id=item.id),
                    view_ref=ViewRef(id=view.id, name=self.view_name),
                    **entity,
                )
            )

            for key, entity_annotation in entity_annotations.items():
                if key not in annotations:
                    annotations[key] = []
                annotations[key].extend(entity_annotation)
        return entities, annotations

    def _read_metadata(self, metadata_file: Path) -> list[dict]:
        if not metadata_file.exists():
            raise FileNotFoundError(f"Metadata file {metadata_file} not found")
        return pa_json.read_json(metadata_file).to_pylist()
