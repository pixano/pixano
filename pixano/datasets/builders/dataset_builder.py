import abc
import concurrent
import os
import pathlib
from typing import Any, Dict, Iterator, Type

import duckdb
import lancedb
import lancedb.pydantic
import shortuuid
import tqdm

from pixano.datasets.dataset_schema import DatasetFeatures, DatasetSchema

from .. import dataset
from ..dataset_info import DatasetInfo
from ..features.schemas import image as image_schema
from ..features.schemas import sequence_frame as sequence_frame_schema
from ..utils import video as video_utils


class DatasetBuilder(abc.ABC):
    """Abstract base class for dataset builders.

    Attributes:
        _schemas (dict[str, Any]): The schemas for the dataset tables.
        _target_dir (pathlib.Path): The target directory for the dataset.
        _source_dir (pathlib.Path): The source directory for the dataset.
        _db (lancedb.Database): The lancedb.Database instance for the dataset.
        _previews_path (pathlib.Path): The path to the previews directory.
        _mode (str): The mode for creating the dataset.
    """

    def __init__(
        self,
        source_dir: os.PathLike,
        target_dir: os.PathLike,
        schemas: Type[DatasetFeatures],
        info: DatasetInfo,
        mode: str = "create",
    ):
        """Initialize the BaseDatasetBuilder instance.

        Args:
            source_dir (os.PathLike): The source directory for the dataset.
            target_dir (os.PathLike): The target directory for the dataset.
            schemas (dict[str, Any]): The schemas for the dataset tables.
            info (dict[str, Any]): User informations (name, description, splits)
            for the dataset.
            mode (str, optional): The mode for creating the dataset.

        """
        self._target_dir = pathlib.Path(target_dir)
        self._source_dir = pathlib.Path(source_dir)
        self._previews_path = self._target_dir / dataset.Dataset.PREVIEWS_PATH
        self._mode = mode
        self._info = info
        self._db = lancedb.connect(self._target_dir / dataset.Dataset.DB_PATH)

        self._dataset_schema: DatasetSchema = schemas.to_dataset_schema()
        self._schemas = self._dataset_schema.schemas

    def build(self) -> dataset.Dataset:
        """Build the dataset.

        Returns:
            Dataset: The built dataset.

        """
        tables = self._create_tables()

        for count, items in enumerate(
            tqdm.tqdm(self._generate_items(), desc="Import items")
        ):
            # Assert that items and tables have the same keys
            # assert set(items.keys()) == set(
            #     tables.keys()
            # ), "Keys of 'items' and 'tables' do not match"

            for table_name, table in tables.items():
                if table_name == "objects" and len(items[table_name]) == 0:
                    continue
                if table_name not in items:
                    continue

                table.add(items[table_name])

        # save info.json
        self._info.id = shortuuid.uuid()
        self._info.num_elements = count + 1
        self._info.to_json(self._target_dir / dataset.Dataset.INFO_FILE)
        # save schema.json

        self._dataset_schema.to_json(self._target_dir / dataset.Dataset.SCHEMA_FILE)

    @abc.abstractmethod
    def _generate_items(self) -> Iterator[Dict[str, Any]]:
        """Read items from the source directory.

        Returns:
            Iterator[Dict[str, Any]]: An iterator over the items following data schema.

        """
        raise NotImplementedError

    def generate_media_previews(self, **kwargs):
        """Generate media previews for the dataset."""
        for table_name, schema in self._schemas.items():
            print(f"Will generate previews for {table_name}")
            if image_schema.is_image(schema):
                self._generate_image_previews(table_name)
            elif sequence_frame_schema.is_sequence_frame(schema):
                fps = kwargs.get("fps", 25)
                scale = kwargs.get("scale", 0.5)
                self._generate_sequence_frame_previews(table_name, fps, scale)
            else:
                continue

    def _create_tables(self):
        """Create tables in the database.

        Args:
            schemas (dict[str, Any], optional): The schemas for the tables.

        """
        tables = {}
        for key, schema in self._schemas.items():
            self._db.create_table(key, schema=schema, mode=self._mode)

            tables[key] = self._db.open_table(key)

        return tables

    def _generate_image_previews(self):
        """Generate image previews for the dataset."""
        pass

    def _generate_sequence_frame_previews(
        self, table_name: str, fps: int, scale: float
    ):
        """Generate video (sequence frames) previews for the dataset."""
        sequence_table = self._db.open_table(table_name).to_lance()  # noqa: F841

        frames = (
            duckdb.query(
                """SELECT sequence_id, LIST(url) as url, LIST(timestamp) as timestamp
                   FROM sequence_table GROUP BY sequence_id"""
            )
            .to_df()
            .to_dict(orient="records")
        )

        # store previews in the previews directory
        # {previews_path}/{table_name}/{item_id}.mp4
        previews_path = self._previews_path / table_name
        if not previews_path.exists():
            previews_path.mkdir(parents=True)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for seq in frames:
                sorted_frames = sorted(
                    zip(seq["url"], seq["timestamp"]), key=lambda x: x[1]
                )
                im_urls = [self._source_dir / url for url, _ in sorted_frames]
                output_path = previews_path / f"{seq['sequence_id']}.mp4"
                futures.append(
                    executor.submit(
                        video_utils.create_video_preview,
                        output_path,
                        im_urls,
                        fps=fps,
                        scale=scale,
                    )
                )

            for _ in tqdm.tqdm(
                concurrent.futures.as_completed(futures),
                total=len(futures),
                desc=f"Generate previews for {table_name}",
            ):
                pass
