from pathlib import Path
from typing import Any, Iterator

import PIL
import pyarrow.json as pa_json
import shortuuid
from s3path import S3Path

from pixano.datasets.features.schemas.base_schema import BaseSchema

from ..features.schemas.image import Image, is_image
from ..features.types.bbox import BBox, is_bbox
from .dataset_builder import DatasetBuilder


class FolderBasedBuilder(DatasetBuilder):
    """This is a class for building datasets based on folder structure."""

    # build data from folder follwing a specific structure
    # - source_dir/{split}/{item}.{ext}
    # - source_dir/{split}/metadata.jsonl

    METADATA_FILENAME = "metadata.jsonl"
    EXTENSIONS: list[str]

    def _generate_items(
        self,
    ) -> Iterator[dict[str, Any]]:
        for split in self._source_dir.glob("*"):
            if split.is_dir() and not split.name.startswith("."):
                metadata = self._read_metadata(split / self.METADATA_FILENAME)

                # only consider {split}/{item}.{ext} files

                # For a single view expect only 1 schema to be an Image
                # TODO: handle other view types
                for k, s in self._schemas.items():
                    if is_image(s):
                        view_name = k
                        break

                for view_file in split.glob("*"):
                    if view_file.is_file() and view_file.suffix in self.EXTENSIONS:
                        # create item
                        item_metadata = {}
                        for m in metadata:
                            if m[view_name] == view_file.name:
                                item_metadata = m
                                break

                        item = self._create_item(split.name, item_metadata)

                        # create view
                        view = self._create_view(item, view_file, view_name)

                        # creat objects
                        objects = self._create_objects(item.id, view_name, item_metadata)

                        yield {
                            "item": [item],
                            "image": [view],
                            "objects": objects,
                        }

    def _create_item(self, split, item_metadata) -> BaseSchema:
        # find in metadata if view_file.name is present in the unique views

        return self._schemas["item"](
            id=shortuuid.uuid(),
            split=split,
            **item_metadata,
        )

    def _create_view(self, item, view_file, view_name) -> Image:
        if is_image(self._schemas[view_name]):
            img = PIL.Image.open(view_file)
            view = Image(
                id=shortuuid.uuid(),
                item_id=item.id,
                url=view_file.relative_to(self._source_dir).as_posix(),
                width=img.width,
                height=img.height,
                format=img.format,
            )
        else:
            raise ValueError(
                f"View type {self._schemas[view_name]} or {view_name} not supported"
            )

        return view

    def _create_objects(self, item_id, view_name, item_metadata):
        # if item has objects annotated in the metadata return it
        # else return an empty list
        if "objects" not in item_metadata or item_metadata["objects"] is None:
            return []

        objects = []
        # TODO: change this hardcoded key
        obj_data = item_metadata["objects"]

        # TODO: check obj_attrs match the schema
        obj_attrs = list(obj_data.keys())
        num_objects = len(obj_data[obj_attrs[0]])

        for i in range(num_objects):
            obj = {}
            for attr in obj_attrs:
                if is_bbox(
                    self._schemas["objects"].model_fields[attr].annotation,
                ):
                    obj[attr] = BBox(
                        coords=obj_data[attr][i],
                        format="xywh",
                        is_normalized=True,
                        confidence=1.0,
                    )
                else:
                    obj[attr] = obj_data[attr][i]

            objects.append(
                self._schemas["objects"](
                    id=shortuuid.uuid(),
                    item_id=item_id,
                    view_id=view_name,
                    **obj,
                )
            )

        return objects

    def _read_metadata(self, metadata_file: Path | S3Path) -> list[dict]:
        if metadata_file.exists():
            return pa_json.read_json(metadata_file).to_pylist()
        else:
            raise FileNotFoundError(f"Metadata file {metadata_file} not found")
