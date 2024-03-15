import os
import typing

import PIL
import pyarrow.json as pa_json
import shortuuid

from ...core import types as pix_types
from . import dataset_builder


class FolderBasedBuilder(dataset_builder.DatasetBuilder):
    # build data from folder follwing a specific structure
    # - source_dir/{split}/{item}.{ext}
    # - source_dir/{split}/metadata.jsonl

    METADATA_FILENAME = "metadata.jsonl"
    EXTENSIONS: list[str]

    def __init__(self, source_dir, target_dir, schemas, info, mode="create"):
        super().__init__(source_dir, target_dir, schemas, info, mode=mode)

    def _generate_items(
        self,
    ) -> dataset_builder.Iterator[dataset_builder.Dict[str, typing.Any]]:
        for split in self._source_dir.glob("*"):
            if split.is_dir() and not split.name.startswith("."):
                metadata = self._read_metadata(split / self.METADATA_FILENAME)

                # only consider {split}/{item}.{ext} files
                for view_file in split.glob("*"):
                    if view_file.is_file() and view_file.suffix in self.EXTENSIONS:
                        # create item
                        item = self._create_item(split.name, view_file, metadata)

                        # create view
                        view = self._create_view(item)

                        # creat objects
                        objects = self._create_objects(item, metadata)

                        yield {
                            "item": [item],
                            "image": [view],
                            "objects": objects,
                        }

    def _create_item(self, split, view_file, metadata):
        # For a single view expect only 1 schema to be an Image
        # TODO: handle other view types
        for k, s in self._schemas.items():
            if issubclass(pix_types.Image, s):
                view_name = k
                break

        # keep only the last two parts of the path to get the relative path
        # {split}/*.ext
        parts = list(view_file.parts)
        relative_path = "/".join(parts[-2:])
        view_records = pix_types.ViewRecords(
            ids=["view0"],
            names=[view_name],
            paths=[relative_path],
        )

        # find in metadata if view_file.name is present in the unique views
        item_metadata = {}
        for m in metadata:
            if m[view_name] == view_file.name:
                item_metadata = m
                break

        return self._schemas["item"](
            id=shortuuid.uuid(),
            views=view_records,
            split=split,
            **item_metadata,
        )

    def _create_view(self, item):
        view_name = item.views.names[0]
        if issubclass(pix_types.Image, self._schemas[view_name]):
            img = PIL.Image.open(self._source_dir / item.views.paths[0])
            view = pix_types.Image(
                id=shortuuid.uuid(),
                item_id=item.id,
                url=item.views.paths[0],
                width=img.width,
                height=img.height,
                format=img.format,
            )
        else:
            raise ValueError(
                f"View type {self._schemas[view_name]} or {view_name} not supported"
            )

        return view

    def _create_objects(self, item, metadata):
        # if item has objects annotated in the metadata return it
        # else return an empty list
        objects = []
        for m in metadata:
            if m[item.views.names[0]] == item.views.paths[0].split("/")[-1]:
                # TODO: change this hardcoded key
                obj_data = m["objects"]

                # TODO: check obj_attrs match the schema
                obj_attrs = list(obj_data.keys())
                num_objects = len(obj_data[obj_attrs[0]])

                for i in range(num_objects):
                    obj = {}
                    for attr in obj_attrs:
                        if issubclass(
                            self._schemas["objects"].model_fields[attr].annotation,
                            pix_types.BBox,
                        ):
                            obj[attr] = pix_types.BBox(
                                coords=obj_data[attr][i],
                                format="xywh",
                                is_normalized=False,
                                confidence=1.0,
                            )
                        else:
                            obj[attr] = obj_data[attr][i]

                    objects.append(
                        self._schemas["objects"](
                            id=shortuuid.uuid(),
                            item_id=item.id,
                            view_id=item.views.ids[0],
                            **obj,
                        )
                    )

        return objects

    def _read_metadata(self, metadata_file: os.PathLike) -> list[dict]:
        if metadata_file.exists():
            return pa_json.read_json(metadata_file).to_pylist()
        else:
            raise FileNotFoundError(f"Metadata file {metadata_file} not found")
