# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path
from typing import Any, Iterator, Mapping

import pyarrow.json as pa_json
import shortuuid

from pixano.datasets.dataset_library import DatasetLibrary
from pixano.datasets.dataset_schema import DatasetItem
from pixano.datasets.features.schemas.base_schema import BaseSchema
from pixano.datasets.features.schemas.item import Item
from pixano.datasets.features.schemas.object import Object
from pixano.datasets.features.schemas.registry import _PIXANO_SCHEMA_REGISTRY
from pixano.datasets.features.schemas.view import View
from pixano.datasets.features.types.registry import _ATOMIC_PYTHON_TYPES, _TYPES_REGISTRY
from pixano.datasets.features.utils import create_row
from pixano.datasets.features.utils.creators import create_pixano_object

from ...features.types.bbox import create_bbox, is_bbox
from ..dataset_builder import DatasetBuilder


class FolderBaseBuilder(DatasetBuilder):
    """This is a class for building datasets based on a folder structure.

    The folder structure should be as follows:
    - source_dir/{split}/{item}.{ext}
    - source_dir/{split}/metadata.jsonl
    Only one view  is supported in folder based builders.

    The metadata file should be a jsonl file with the following format:
    .. code-block:: json
    [
        {
            "item": "item1",
            "metadata1": "value1",
            "metadata2": "value2",
            ...
            "objects": {
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
            "objects": {
                "attr1": [val1, val2, ...],
                "attr2": [val1, val2, ...],
                ...
            }
        },
        ...
    ]

    Attributes:
        view_name (str): The name of the view.
        view_schema (type[View]): The schema of the view.
        METADATA_FILENAME (str): The metadata filename.
        OBJECTS_KEY (str): The key for the objects in the metadata file.
        EXTENSIONS (list[str]): The list of supported extensions.
    """

    METADATA_FILENAME: str = "metadata.jsonl"
    OBJECTS_KEY: str = "objects"
    EXTENSIONS: list[str]

    def __init__(
        self, source_dir: Path | str, target_dir: Path | str, schemas: type[DatasetItem], info: DatasetLibrary
    ) -> None:
        """Initialize the FolderBaseBuilder.

        Args:
            source_dir (Path | str): The source directory for the dataset.
            target_dir (Path | str): The target directory for the dataset.
            schemas (type[DatasetItem]): The schemas for the dataset tables.
            info (DatasetLibrary): User informations (name, description, ...)
            for the dataset.
        """
        super().__init__(source_dir, target_dir, schemas, info)
        view_name = None
        for k, s in self.schemas.items():
            if issubclass(s, View):
                if view_name is not None:
                    raise ValueError("Only one view type is supported in folder based builders")
                view_name = k
                view_schema = s
        self.view_name = view_name
        self.view_schema = view_schema

    def _generate_items(
        self,
    ) -> Iterator[dict[str, BaseSchema | list[BaseSchema]]]:
        """Read items from the folder directory.

        Returns:
            Iterator[dict[str, BaseSchema | list[BaseSchema]]]: An iterator over the items following data schema.

        """
        for split in self.source_dir.glob("*"):
            if split.is_dir() and not split.name.startswith("."):
                metadata = self._read_metadata(split / self.METADATA_FILENAME)

                for view_file in split.glob("*"):
                    # only consider {split}/{item}.{ext} files
                    if view_file.is_file() and view_file.suffix in self.EXTENSIONS:
                        # retrieve item metadata in metadata file
                        item_metadata = {}
                        for m in metadata:
                            if m[self.view_name] == view_file.name:
                                item_metadata = m
                                break
                        if not item_metadata:
                            raise ValueError(f"Metadata not found for {view_file}")

                        # extract object metadata from item metadata
                        objects_data = item_metadata.pop(self.OBJECTS_KEY, None)

                        # create item
                        item = self._create_item(split.name, **item_metadata)

                        # create view
                        view = self._create_view(item, view_file, self.view_schema)

                        if objects_data is None:
                            yield {
                                self.item_schema_name: item,
                                self.view_name: view,
                            }
                            continue

                        # create objects
                        objects = self._create_objects(item, view, objects_data)

                        yield {
                            self.item_schema_name: item,
                            self.view_name: view,
                            self.OBJECTS_KEY: objects,
                        }

    def _create_item(self, split: str, **item_metadata) -> BaseSchema:
        return self.item_schema(
            id=shortuuid.uuid(),
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

        return create_row(view_schema, item_id=item.id, url=view_file, other_path=self.source_dir)

    def _create_objects(self, item: Item, view: View, objects_data: dict[str, Any]) -> list[Object]:
        objects = []

        obj_attrs = list(objects_data.keys())
        for attr in obj_attrs:
            if attr not in self.schemas[self.OBJECTS_KEY].model_fields:
                raise ValueError(f"Attribute {attr} not found in object schema.")

        # check if all list of objects data have same length
        nums_objects = {len(v) if isinstance(v, list) else 1 for v in objects_data.values() if v is not None}
        if len(nums_objects) > 1:
            raise ValueError("All list of objects data must have same length")
        elif len(nums_objects) == 0:
            return []

        num_objects = nums_objects.pop()
        objects_data = {k: v if isinstance(v, list) else [v] for k, v in objects_data.items() if v is not None}
        obj_attrs = list(objects_data.keys())
        for i in range(num_objects):
            object = {}
            for attr in obj_attrs:
                if objects_data[attr] is None:
                    continue

                is_attr_pix_type = self.schemas[self.OBJECTS_KEY].model_fields[attr].annotation in set(
                    _TYPES_REGISTRY.values()
                ) - set(_ATOMIC_PYTHON_TYPES)
                if is_attr_pix_type:
                    pix_type = self.schemas[self.OBJECTS_KEY].model_fields[attr].annotation
                    if isinstance(objects_data[attr][i], Mapping):
                        object[attr] = create_pixano_object(
                            pix_type,
                            **objects_data[attr][i],
                        )
                    else:
                        # TODO check jsonl format for mask & keypoints
                        if is_bbox(pix_type, True):
                            object[attr] = create_bbox(
                                objects_data[attr][i],
                                format="xywh",
                                is_normalized=True,
                                confidence=1.0,
                            )
                        else:
                            raise ValueError(f"Type {pix_type} not supported for infered object creation.")
                else:
                    object[attr] = objects_data[attr][i]
            objects.append(
                self.schemas[self.OBJECTS_KEY](
                    id=shortuuid.uuid(),
                    item_id=item.id,
                    view_id=view.id,
                    **object,
                )
            )

        return objects

    def _read_metadata(self, metadata_file: Path) -> list[dict]:
        if not metadata_file.exists():
            raise FileNotFoundError(f"Metadata file {metadata_file} not found")
        return pa_json.read_json(metadata_file).to_pylist()
