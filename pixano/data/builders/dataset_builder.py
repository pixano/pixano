import abc
import concurrent
import json
import os
import pathlib
from typing import (
    Any,
    Dict,
    Iterator,
    List,
    Optional,
    Type,
    _GenericAlias,
)

import duckdb
import lancedb
import pydantic
import pydantic_core
import tqdm

# from ...... import sequence_utils
from ...features import schemas as table_schemas
from ..dataset import dataset


def _generate_schema_mapping(cls):
    # extra item fields infered from the cls
    item_fields = {}

    # table schemas
    schemas = {}

    for field_name, field in cls.model_fields.items():
        if isinstance(field.annotation, _GenericAlias):
            origin = field.annotation.__origin__
            args = field.annotation.__args__

            if origin == list or origin == List:
                if issubclass(args[0], table_schemas.Object):
                    # Categorizing List of Object as objects
                    schemas[field_name] = args[0]
                else:
                    # Handling list of simple types (e.g., List[float])
                    default_value = (
                        ...
                        if isinstance(
                            field.default, pydantic_core.PydanticUndefinedType
                        )
                        else field.default
                    )
                    item_fields[field_name] = (list[args[0]], default_value)
            else:
                # Default case: categorize as item attribute
                item_fields[field_name] = (args[0], default_value)
        elif issubclass(field.annotation, table_schemas.Image):
            # Categorizing Image as a view
            schemas[field_name] = field.annotation
        else:
            default_value = (
                ...
                if isinstance(field.default, pydantic_core.PydanticUndefinedType)
                else field.default
            )
            # Default case: categorize as item attribute
            item_fields[field_name] = (field.annotation, default_value)

    DatasetItem = pydantic.create_model(
        cls.__name__, **item_fields, __base__=table_schemas.Item
    )

    schemas["item"] = DatasetItem

    return schemas


class DatasetInfo(pydantic.BaseModel):
    """Metadata for a dataset.

    Attributes:
        name (str): The name of the dataset.
        description (str, optional): The description of the dataset.
        id (str, optional): The ID of the dataset.
        estimated_size (int, optional): The estimated size of the dataset.
        num_elements (int, optional): The number of elements in the dataset.

    Methods:
        from_json(cls, path): Create a DatasetInfo instance from a JSON file.

    """

    name: str
    description: Optional[str] = None
    id: Optional[str] = None
    estimated_size: Optional[int] = None
    num_elements: Optional[int] = None

    @classmethod
    def from_json(cls, path: os.PathLike):
        """Create a DatasetInfo instance from a JSON file.

        Args:
            path (os.PathLike): The path to the JSON file.

        Returns:
            DatasetInfo: The created DatasetInfo instance.

        """
        with open(path, "r") as f:
            data = json.load(f)
        return cls(**data)


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
        schemas: Type[Any],
        info: DatasetInfo,
        mode: str = "create",
    ):
        """Initialize the BaseDatasetBuilder instance.

        Args:
            source_dir (os.PathLike): The source directory for the dataset.
            target_dir (os.PathLike): The target directory for the dataset.
            schemas (dict[str, Any]): The schemas for the dataset tables.
            info (DatasetInfo): The DatasetInfo instance for the dataset.
            mode (str, optional): The mode for creating the dataset.

        """
        self._schemas = _generate_schema_mapping(schemas)
        self._target_dir = pathlib.Path(target_dir)
        self._source_dir = pathlib.Path(source_dir)
        self._previews_path = self._target_dir / dataset.Dataset.DEFAULT_PREVIEWS_PATH
        self._mode = mode

        self._db = lancedb.connect(self._target_dir / dataset.Dataset.DEFAULT_DB_PATH)

        # self._info = info.model_copy(update={"id": shortuuid.uuid()})

    def build(self) -> dataset.Dataset:
        """Build the dataset.

        Returns:
            Dataset: The built dataset.

        """
        self._create_tables(self._schemas)

        tables = {k: self._db.open_table(k) for k in self._schemas.keys()}

        for items in tqdm.tqdm(self._generate_items(), desc="Import items"):
            # Assert that items and tables have the same keys
            assert set(items.keys()) == set(
                tables.keys()
            ), "Keys of 'items' and 'tables' do not match"

            for table_name, table in tables.items():
                if table_name == "objects" and len(items[table_name]) == 0:
                    continue

                table.add(items[table_name])

    def generate_rgb_sequence_preview(self, fps: int = 25, scale: float = 0.5):
        """Generate RGB sequence previews for the dataset.

        Args:
            fps (int, optional): The frames per second for the preview.
            scale (float, optional): The scale factor for the preview.

        """
        items_table = self._db.open_table(TableType.ITEM).to_lance()
        ids_and_views = duckdb.query("SELECT id, views FROM items_table").to_df()

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            sequences_table = self._db.open_table(TableType.RGB_SEQUENCE).to_lance()

            futures = []
            for _, row in ids_and_views.iterrows():
                for n, view_id in enumerate(row["views"]["ids"]):
                    im_urls = duckdb.query(
                        f"SELECT url FROM sequences_table WHERE item_id LIKE '{row['id']}' AND view_id LIKE '{view_id}' ORDER BY timestamp "
                    ).to_df()
                    im_urls = im_urls["url"].tolist()
                    previews_path = self._previews_path / f"{row['views']['names'][n]}"
                    if not previews_path.exists():
                        previews_path.mkdir(parents=True)
                    output_path = previews_path / f"{row['id']}.mp4"
                    futures.append(
                        executor.submit(
                            sequence_utils.create_video_preview,
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
    def _generate_items(self) -> Iterator[Dict[str, Any]]:
        """Read items from the source directory.

        Returns:
            Iterator[Dict[str, Any]]: An iterator over the items following data schema.

        """
        raise NotImplementedError

    def _create_tables(self, schemas: dict[str, Any] = None):
        """Create tables in the database.

        Args:
            schemas (dict[str, Any], optional): The schemas for the tables.

        """
        for key, schema in schemas.items():
            self._db.create_table(key, schema=schema, mode=self._mode)
