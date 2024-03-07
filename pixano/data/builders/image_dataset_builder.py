from typing import Iterator, List

import PIL
import shortuuid

from ...core import types as pix_types
from . import base_dataset_builder


class ImageDatasetBuilder(base_dataset_builder.BaseDatasetBuilder):

    def __init__(self, source_dir, target_dir, schemas, info, mode="create"):
        super().__init__(source_dir, target_dir, schemas, info, mode=mode)

    def _read_items(self) -> Iterator[list[pix_types.Item]]:
        for f in self._source_dir.glob("**/*"):
            if f.is_file() and f.suffix in [".jpg", ".jpeg", ".png"]:
                split = f.parent.stem
                parts = list(f.parts)
                view_file = "/".join(parts[-2:])

                yield [
                    self._schemas["item"](
                        id=shortuuid.uuid(),
                        views=pix_types.ViewRecords(names=["image"], paths=[view_file]),
                        split=split,
                    )
                ]

    def _read_views_for_items(self, items: List[pix_types.Item]):
        views = {}

        for item in items:
            for i, v in enumerate(item.views.names):
                if not v in views:
                    views[v] = []

                # TODO check view type and choose correct reader
                image = PIL.Image.open(self._source_dir / item.views.paths[i])
                views[v].append(
                    pix_types.Image(
                        id=shortuuid.uuid(),
                        item_id=item.id,
                        url=item.views.paths[i],
                        width=image.width,
                        height=image.height,
                        format=image.format,
                    )
                )

        return views
