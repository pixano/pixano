# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Mapping

import pyarrow.json as pa_json
import shortuuid

from pixano.datasets.dataset_info import DatasetInfo
from pixano.datasets.dataset_schema import DatasetItem
from pixano.datasets.utils import mosaic
from pixano.datasets.workspaces import WorkspaceType
from pixano.features import (
    BaseSchema,
    Entity,
    Item,
    Message,
    View,
    create_bbox,
    create_conversation,
    is_annotation,
    is_bbox,
    is_conversation,
    is_entity,
    is_view,
)
from pixano.features.schemas.annotations import Annotation
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
        Only one view is supported in folder builders. If you give a list of images, it will be put in a mosaic.

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
        media_dir: Path | str,
        library_dir: Path | str,
        info: DatasetInfo,
        dataset_path: Path | str,
        dataset_item: type[DatasetItem] | None = None,
        use_image_name_as_id: bool = False,
    ) -> None:
        """Initialize the `FolderBaseBuilder`.

        Args:
            media_dir: The global media directory.
            library_dir: The global directory for Pixano datasets library.
            dataset_item: The dataset item schema.
            info: User informations (name, description, ...) for the dataset.
            dataset_path: Path to dataset, relative to media_dir.
            use_image_name_as_id: If True, use image base name as image id.
                                  Images MUST have unique base names.
                                  When no metadata file exists, also use it as item id,
                                  else, use 'item_#'
                                  This allows to reuse image embeddings after dataset overwrite.
        """
        info.workspace = self.WORKSPACE_TYPE
        if self.DEFAULT_SCHEMA is not None and dataset_item is None:
            dataset_item = self.DEFAULT_SCHEMA
        if dataset_item is None:
            raise ValueError("A schema is required.")

        self.use_image_name_as_id = use_image_name_as_id

        self.media_dir = Path(media_dir)
        dataset_path = Path(dataset_path)
        self.source_dir = self.media_dir / dataset_path
        if not self.source_dir.is_dir():
            raise ValueError("A source path (media_dir / dataset_path) is required.")

        target_dir = Path(library_dir) / "_".join(dataset_path.parts)
        super().__init__(target_dir=target_dir, dataset_item=dataset_item, info=info)

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

        # TODO - allow multiview in base FolderBuilder
        if len(self.views_schema) > 1:
            raise ValueError("Only one view schema is supported in folder based builders.")

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
                for view_file in sorted(split.glob("**/*")):
                    # only consider {split}/**/{item}.{ext} files
                    if not view_file.is_file() or view_file.suffix not in self.EXTENSIONS:
                        continue
                    # create item with default values for custom fields
                    custom_item_metadata = self._build_default_custom_metadata_item()
                    custom_item_metadata["id"] = view_file.stem
                    custom_item_metadata["split"] = split.name
                    item = self._create_item(**custom_item_metadata)
                    # create view
                    view_name_nojsonl, view_schema_nojsonl = list(self.views_schema.items())[0]  # only one view
                    view = self._create_view(item, view_file, view_schema_nojsonl)
                    yield {
                        self.item_schema_name: item,
                        view_name_nojsonl: view,
                    }
                    # if schema contain a Conversation, add one
                    for entity_name, entity_schema_nojsonl in self.entities_schema.items():
                        if entity_schema_nojsonl is not None and is_conversation(entity_schema_nojsonl):
                            default_view_ref = ViewRef(id=view.id, name=view_name_nojsonl)
                            conversation = create_conversation(
                                id=shortuuid.uuid(),
                                kind="vqa",
                                item_ref=ItemRef(id=item.id),
                                view_ref=default_view_ref,
                            )
                            yield {"conversations": conversation}

                continue

            for i, dataset_piece in enumerate(dataset_pieces):
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

                # create view
                views_data: list[tuple[str, View]] = []
                for k, v in dataset_piece.items():
                    if k in self.views_schema:
                        view_name = k
                        view_schema = self.views_schema.get(view_name)
                        if view_schema is not None:
                            if isinstance(v, list):
                                if len(v) == 0:
                                    continue
                                if len(v) > 1:
                                    # create a mosaic from item images
                                    mosaic_file = mosaic(self.source_dir, split.name, v, view_name)
                                    view_file = self.source_dir / mosaic_file
                                    if not view_file.is_file():  # no split path in metadata.jsonl
                                        view_file = self.source_dir / split.name / mosaic_file
                                else:
                                    view_file = self.source_dir / Path(v[0])
                                    if not view_file.is_file():  # no split path in metadata.jsonl
                                        view_file = self.source_dir / split.name / Path(v[0])
                                if view_file.is_file() and view_file.suffix in self.EXTENSIONS:
                                    view = self._create_view(item, view_file, view_schema)
                                    views_data.append((view_name, view))
                            else:
                                view_file = self.source_dir / (
                                    Path(v) if split.name == Path(v).parts[0] else split / Path(v)
                                )
                                if view_file.is_file() and view_file.suffix in self.EXTENSIONS:
                                    view = self._create_view(item, view_file, view_schema)
                                    views_data.append((view_name, view))

                all_entities_data: dict[str, list[Entity]] = defaultdict(list)
                all_annotations_data: dict[str, list[Annotation]] = defaultdict(list)
                for k, v in dataset_piece.items():
                    if k in self.entities_schema and v is not None:
                        entity_name = k
                        raw_entities_data = v
                        entity_schema = self.entities_schema.get(entity_name)
                        if entity_schema is not None:
                            if is_conversation(entity_schema):
                                entities_data, annotations_data = self._create_vqa_entities(
                                    item, views_data, entity_name, entity_schema, raw_entities_data
                                )
                            else:  # classic entity
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

    def _create_vqa_entities(
        self,
        item: Item,
        views_data: list[tuple[str, View]],
        entity_name: str,
        entity_schema: type[Entity],
        raw_entities_data: list[Any],
    ) -> tuple[dict[str, list[Entity]], dict[str, list[Annotation]]]:
        def update_viewref(content, views_data, view_ref):
            match = re.match(r".*<image (\d)>.*", content)  # TODO image_regex as parameter
            if match is None:
                return view_ref
            for m in match.groups():
                num = int(m) - 1
                if num >= 0 and num < len(views_data):
                    view_name, view = views_data[num]
                    return ViewRef(id=view.id, name=view_name)
            return view_ref

        entities: dict[str, list[Entity]] = defaultdict(list)
        annotations: dict[str, list[Annotation]] = defaultdict(list)

        default_user = "import"
        entities_data: list[list[Any]] = []

        if isinstance(raw_entities_data, list):
            if all(isinstance(data, list) for data in raw_entities_data):
                entities_data = raw_entities_data
            if all(isinstance(data, dict) for data in raw_entities_data):
                entities_data = [raw_entities_data]

        for conv in entities_data:
            view_name, view = views_data[0]  # Only one view
            default_view_ref = ViewRef(id=view.id, name=view_name)

            conversation = entity_schema(
                id=shortuuid.uuid(), kind="vqa", item_ref=ItemRef(id=item.id), view_ref=default_view_ref
            )
            entities[entity_name].append(conversation)

            for i, q_n_a in enumerate(conv):
                question = q_n_a.get("question")
                if not question:
                    raise ValueError(f"No question found for item {item}")

                # Handle question
                if "user" not in question:
                    question["user"] = default_user

                content = question.get("content")
                if not content:
                    raise ValueError(f"No text content found for question in item {item}")

                view_ref = update_viewref(content, views_data, default_view_ref)

                query_msg = Message(
                    id=shortuuid.uuid(),
                    number=i,
                    type="QUESTION",
                    item_ref=ItemRef(id=item.id),
                    entity_ref=EntityRef(id=conversation.id, name=entity_name),
                    source_ref=SourceRef(id=self.source_id),
                    view_ref=view_ref,
                    timestamp=datetime.now(),
                    **question,
                )
                annotations["messages"].append(query_msg)

                # Handle all responses

                responses = []
                response = q_n_a.get("response", None)
                if isinstance(response, dict):
                    responses = [response]
                if not responses:
                    responses = q_n_a.get("responses", [])
                    if not isinstance(responses, list):
                        responses = [responses]

                for response in responses:
                    if "user" not in response:
                        response["user"] = default_user
                    content = response.get("content", "")
                    explanation = response.get("explanation", "")
                    if query_msg.question_type != "OPEN":
                        response["content"] = "[[{}]] {}".format(content, explanation)

                    response_msg = Message(
                        id=shortuuid.uuid(),
                        number=i,
                        type="ANSWER",
                        question_type=query_msg.question_type,
                        item_ref=ItemRef(id=item.id),
                        entity_ref=EntityRef(id=conversation.id, name=entity_name),
                        source_ref=SourceRef(id=self.source_id),
                        timestamp=datetime.now(),
                        **response,
                    )
                    annotations["messages"].append(response_msg)
        return entities, annotations

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

        # only one view
        view_name, view = views_data[0]

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
                            view_ref=ViewRef(id=view.id, name=view_name),
                            entity_ref=EntityRef(id=entity_id, name=entity_name),
                            source_ref=SourceRef(id=self.source_id),
                            **entities_data[attr][i],
                        )
                    else:
                        # TODO check jsonl format for mask & keypoints
                        if is_bbox(schema, True):
                            annotation = create_bbox(
                                id=shortuuid.uuid(),
                                item_ref=ItemRef(id=item.id),
                                view_ref=ViewRef(id=view.id, name=view_name),
                                entity_ref=EntityRef(id=entity_id, name=entity_name),
                                source_ref=SourceRef(id=self.source_id),
                                coords=entities_data[attr][i],
                                format="xywh",
                                is_normalized=all(0 <= x <= 1 for x in entities_data[attr][i]),
                                confidence=1.0,
                            )
                        else:
                            raise ValueError(f"Schema {schema} not supported for infered entity creation.")
                    entity_annotations[attr].append(annotation)
                else:
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
