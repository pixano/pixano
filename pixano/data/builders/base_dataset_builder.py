import abc
import concurrent
import json
import os
import pathlib
from enum import Enum
from typing import Any, Iterator, Optional

import duckdb
import lancedb

# import pyarrow as pa
import pydantic
import tqdm
from lancedb.pydantic import LanceModel

# from ...... import sequence_utils
# from ...core import pydantic_utils
from ...core import types as pix_types


DEFAULT_DATASET_INFO_FILE = "db.json"
DEFAULT_DATASET_PATH = "db"
DEFAULT_PREVEWS_PATH = "previews"


class TableType(Enum):
    """TableType."""

    ITEM = "item"
    RGB_IMAGE = "image"
    RGB_SEQUENCE = "rgb_sequence"
    DEPTH_IMAGE = "depth_image"
    PCL = "pcl"
    PCL_SEQUENCE = "pcl_sequence"
    OBJECT = "object"

    def __str__(self):  # noqa: D105
        return self.value


class DatasetInfo(pydantic.BaseModel):
    """DatasetInfo."""

    # initial metadata set by the user from config file or dict
    name: str
    description: Optional[str] = None

    # set by the builder
    id: Optional[str] = None

    # set by the builder after generating the dataset
    estimated_size: Optional[int] = None
    num_elements: Optional[int] = None

    @classmethod
    def from_json(cls, path: os.PathLike):
        """Read DatasetInfo from JSON file."""
        with open(path, "r") as f:
            data = json.load(f)
        return cls(**data)


class Dataset:
    """Dataset.

    Args:
        path (os.PathLike): Dataset path
        info (Optional[DatasetInfo], optional): Dataset info. Defaults to None.
    """

    def __init__(self, path: os.PathLike, info: Optional[DatasetInfo] = None):  # noqa: D107
        self._path = pathlib.Path(path)
        self._db = lancedb.connect(self._path / DEFAULT_DATASET_PATH)

        if info is not None:
            self._info = info
        elif (self._path / DEFAULT_DATASET_INFO_FILE).exists():
            self._info = DatasetInfo.from_json((self._path / DEFAULT_DATASET_INFO_FILE))
        else:
            raise ValueError(
                "No dataset info provided and no info file found in dataset path"
            )


class BaseDatasetBuilder(abc.ABC):
    """BaseDatasetBuilder.

    Args:
        source_dir (os.PathLike): Source directory
        target_dir (os.PathLike): Target directory
        schemas (dict[str, Any]): Schemas
        info (DatasetInfo): Dataset info
        mode (str, optional): Mode. Defaults to "create".
    """

    def __init__(  # noqa: D107
        self,
        source_dir: os.PathLike,
        target_dir: os.PathLike,
        schemas: dict[str, Any],
        info: DatasetInfo,
        mode: str = "create",
    ):
        self._schemas = schemas
        self._target_dir = pathlib.Path(target_dir)
        self._source_dir = pathlib.Path(source_dir)

        self._db = lancedb.connect(self._target_dir / DEFAULT_DATASET_PATH)

        self._previews_path = self._target_dir / DEFAULT_PREVEWS_PATH

        self._mode = mode
        # self._info = info.model_copy(update={"id": shortuuid.uuid()})

    def build(self) -> Dataset:  # noqa: D102
        self._create_tables(self._schemas)

        # todo asset item in schema keys
        items_table = self._db.open_table("item")

        # first import the main items table
        items_table.add(
            # map(
            # pydantic_utils.list_to_record_batch,
            tqdm.tqdm(self._read_items(), desc="Import items")
            # )
        )

        # import views
        items_table_lance = items_table.to_lance()
        view_tables = {
            name: self._db.open_table(name) for name in self._schemas["views"].keys()
        }

        for items_batch in tqdm.tqdm(
            items_table_lance.to_batches(batch_size=20), desc="Import views"
        ):
            items_batch = items_batch.to_pylist()
            items_batch = [self._schemas["item"](**item) for item in items_batch]
            view_batch = self._read_views_for_items(items_batch)

            for views in view_batch:
                for view_id, view_data in views.items():
                    if isinstance(view_data, list) and isinstance(view_data[0], list):
                        # sequence case (like SequenceFrame): each item view have
                        # a list of media
                        for frame in view_data:
                            view_tables[view_id].add(frame)
                    else:
                        # one media by view
                        view_tables[view_id].add(view_data)

        # self._info = self._info.model_copy(
        #     update={
        #         "estimated_size": 10,
        #         "num_elements": len(items_table),
        #     }
        # )

        # with open(self._target_dir / DEFAULT_DATASET_INFO_FILE, "w") as f:
        #     json.dump(self._info.json(), f)

        # return self._create_dataset()

    def generate_rgb_sequence_preview(self, fps: int = 25, scale: float = 0.5):  # noqa: D102
        items_table = self._db.open_table(TableType.ITEM).to_lance()  # noqa: F841
        ids_and_views = duckdb.query("SELECT id, views FROM items_table").to_df()

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            sequences_table = self._db.open_table(TableType.RGB_SEQUENCE).to_lance()  # noqa: F841

            futures = []
            for _, row in ids_and_views.iterrows():
                for n, view_id in enumerate(row["views"]["ids"]):
                    im_urls = duckdb.query(
                        "SELECT url FROM sequences_table WHERE item_id LIKE "
                        f"'{row['id']}' AND view_id LIKE '{view_id}' ORDER BY timestamp"
                    ).to_df()
                    im_urls = im_urls["url"].tolist()
                    previews_path = self._previews_path / f"{row['views']['names'][n]}"
                    if not previews_path.exists():
                        previews_path.mkdir(parents=True)
                    output_path = previews_path / f"{row['id']}.mp4"
                    futures.append(
                        executor.submit(
                            sequence_utils.create_video_preview,  # noqa: F821
                            output_path,
                            im_urls,
                            fps=fps,
                            scale=scale,
                        )
                    )

            for _ in tqdm.tqdm(
                concurrent.futures.as_completed(futures),
                total=len(futures),
                desc="Generate previews",
            ):
                pass

    @abc.abstractmethod
    def _read_items(self) -> Iterator[list[pix_types.Item]]:
        raise NotImplementedError

    def read_views_for_items(  # noqa: D102
        self, items: list[pix_types.Item]
    ) -> Iterator[dict[str, list]]:
        pass

    # def _read_sequences_for_item(
    #     self, item: pix_pydantic.DatItem
    # ) -> list[pix_pydantic.SequenceFrame]:
    #     pass

    def _create_table_element(self, klass: TableType, **kwargs) -> LanceModel:
        """Create an instance of the given class with the provided keyword arguments.

        Args:
            klass (type): The class type to instantiate.
            **kwargs: Keyword arguments to pass to the class constructor.

        Returns:
            object: An instance of the given class.

        Raises:
            ValueError: If the class type is unknown or if no schema is defined for
                the class type.
        """
        if klass not in self._schemas:
            raise ValueError(f"Unknown type: {type}")
        if self._schemas[klass] is None:
            raise ValueError(f"No schema defined for type: {type}")
        return self._schemas[klass](**kwargs)

    def _create_dataset(self):
        return Dataset(self._target_dir, self._info)

    def _create_tables(self, schemas: dict[str, Any] = None):
        for key, schema in schemas.items():
            if isinstance(schema, dict):
                self._create_tables(schema)
            else:
                self._db.create_table(key, schema=schema, mode=self._mode)
