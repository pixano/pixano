# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from types import GenericAlias
from typing import Any, Iterator, Mapping

import numpy as np
import PIL.Image
import pyarrow.json as pa_json
import shortuuid

from pixano.datasets.dataset_info import DatasetInfo
from pixano.datasets.dataset_schema import DatasetItem
from pixano.datasets.utils import mosaic
from pixano.datasets.workspaces import WorkspaceType
from pixano.features import (
    BaseSchema,
    Entity,
    EntityDynamicState,
    Item,
    Message,
    SchemaGroup,
    View,
    create_bbox,
    create_conversation,
    is_annotation,
    is_bbox,
    is_conversation,
    is_entity,
    is_entity_dynamic_state,
    is_sequence_frame,
)
from pixano.features.schemas.annotations import Annotation
from pixano.features.schemas.annotations.compressed_rle import CompressedRLE, is_compressed_rle
from pixano.features.schemas.annotations.tracklet import Tracklet
from pixano.features.schemas.registry import _PIXANO_SCHEMA_REGISTRY
from pixano.features.schemas.source import SourceKind
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
        Multiple views are supported. When entity data in ``metadata.jsonl`` includes a ``"view_name"`` key
        whose value matches a view field name, that entity (and its annotations) will reference the specified
        view. Without ``"view_name"``, the first view is used by default.
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
        embed_media: bool = False,
        target_name: str | None = None,
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
            embed_media: If True, embed media files as blobs directly in the database
                instead of storing filesystem URLs.
            target_name: If provided, use this name for the target directory in the library
                instead of deriving it from dataset_path.
        """
        info.workspace = self.WORKSPACE_TYPE
        if self.DEFAULT_SCHEMA is not None and dataset_item is None:
            dataset_item = self.DEFAULT_SCHEMA
        if dataset_item is None:
            raise ValueError("A schema is required.")

        self.use_image_name_as_id = use_image_name_as_id
        self.embed_media = embed_media
        if self.embed_media:
            info.storage_mode = "embedded"

        self.media_dir = Path(media_dir)
        dataset_path = Path(dataset_path)
        self.source_dir = self.media_dir / dataset_path
        if not self.source_dir.is_dir():
            raise ValueError("A source path (media_dir / dataset_path) is required.")

        if target_name is not None:
            target_dir = Path(library_dir) / target_name
        else:
            target_dir = Path(library_dir) / "_".join(dataset_path.parts)
        super().__init__(target_dir=target_dir, dataset_item=dataset_item, info=info)

        self.views_schema: dict[str, type[View]] = {}
        self.entities_schema: dict[str, type[Entity]] = {}
        self.entity_dynamic_states_schema: dict[str, type[EntityDynamicState]] = {}
        self.annotations_schema: dict[str, type[Annotation]] = {}

        # Populate views_schema from view_columns metadata (original field names → View types)
        for field_name, vc in self.dataset_schema.view_columns.items():
            field = self._dataset_item_cls.model_fields[field_name]
            if isinstance(field.annotation, GenericAlias):
                view_type = field.annotation.__args__[0]
            else:
                view_type = field.annotation
            self.views_schema[field_name] = view_type

        # Populate entities and annotations from schemas (skip media-type tables and item)
        media_table_names = {vc.media_table for vc in self.dataset_schema.view_columns.values()}
        for k, s in self.schemas.items():
            if k in media_table_names or k == SchemaGroup.ITEM.value:
                continue
            if is_entity(s):
                self.entities_schema.update({k: s})
            elif is_entity_dynamic_state(s):
                self.entity_dynamic_states_schema.update({k: s})
            elif is_annotation(s):
                self.annotations_schema.update({k: s})
        if not self.views_schema or not self.entities_schema:
            raise ValueError("At least one View and one Entity schema must be defined in the schemas argument.")

    @staticmethod
    def _normalize_metadata_key(key: str) -> str:
        return key.strip().lower()

    @staticmethod
    def _is_media_path_token(value: str) -> bool:
        token = value.strip()
        if token == "":
            return False
        if any(c in token for c in ("*", "?", "[", "]")):
            return True
        if "/" in token or "\\" in token:
            return True
        suffix = Path(token).suffix
        return suffix != "" and suffix[1:].isalpha()

    def _matches_single_view_payload(self, value: Any) -> bool:
        """Check if a metadata value can be routed to the single declared view field."""
        if len(self.views_schema) != 1:
            return False

        if isinstance(value, str):
            return self._is_media_path_token(value)
        if isinstance(value, list) and value and all(isinstance(v, str) for v in value):
            return all(self._is_media_path_token(v) for v in value)
        return False

    def _matches_entity_payload(self, entity_name: str, value: Any) -> bool:
        """Check if a metadata value matches a declared entity field."""
        if not isinstance(value, dict):
            return False

        entity_schema = self.entities_schema[entity_name]
        allowed_keys = set(entity_schema.model_fields.keys()) | set(self.annotations_schema.keys()) | {"view_name"}
        return any(key in allowed_keys for key in value.keys())

    def _matches_entity_dynamic_state_payload(self, state_name: str, value: Any) -> bool:
        """Check if a metadata value matches a declared entity dynamic state field."""
        if not isinstance(value, dict):
            return False

        state_schema = self.entity_dynamic_states_schema[state_name]
        allowed_keys = set(state_schema.model_fields.keys()) | {"view_name"}
        return any(key in allowed_keys for key in value.keys())

    def _resolve_schema_key_from_value(self, value: Any) -> str | None:
        """Resolve an unknown metadata key from payload shape using declared schema only."""
        candidates: list[str] = []

        if self._matches_single_view_payload(value):
            candidates.append(next(iter(self.views_schema.keys())))

        entity_candidates = [name for name, schema in self.entities_schema.items() if not is_conversation(schema)]
        if len(entity_candidates) == 1 and self._matches_entity_payload(entity_candidates[0], value):
            candidates.append(entity_candidates[0])

        if len(self.entity_dynamic_states_schema) == 1:
            state_name = next(iter(self.entity_dynamic_states_schema.keys()))
            if self._matches_entity_dynamic_state_payload(state_name, value):
                candidates.append(state_name)

        unique_candidates = list(dict.fromkeys(candidates))
        if len(unique_candidates) == 1:
            return unique_candidates[0]
        return None

    def _normalize_dataset_piece_keys(self, dataset_piece: dict[str, Any]) -> dict[str, Any]:
        """Normalize metadata keys to schema field names when mapping is unambiguous."""
        normalized_piece = dict(dataset_piece)
        known_schema_keys = (
            set(self.item_schema.model_fields.keys())
            | set(self.dataset_schema.view_columns.keys())
            | set(self.views_schema.keys())
            | set(self.entities_schema.keys())
            | set(self.entity_dynamic_states_schema.keys())
            | set(self.annotations_schema.keys())
            | {"fps"}
        )
        normalized_to_keys: dict[str, list[str]] = defaultdict(list)
        for schema_key in known_schema_keys:
            normalized_to_keys[self._normalize_metadata_key(schema_key)].append(schema_key)

        for source_key in list(normalized_piece.keys()):
            if source_key in known_schema_keys:
                continue

            source_value = normalized_piece[source_key]
            normalized_source_key = self._normalize_metadata_key(source_key)
            case_insensitive_matches = normalized_to_keys.get(normalized_source_key, [])

            target_key = case_insensitive_matches[0] if len(case_insensitive_matches) == 1 else None
            if target_key is None:
                target_key = self._resolve_schema_key_from_value(source_value)
            if target_key is None:
                continue

            source_value = normalized_piece.pop(source_key)
            if target_key not in normalized_piece:
                normalized_piece[target_key] = source_value

        return normalized_piece

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
                    view = self._create_view(item, view_file, view_name_nojsonl, view_schema_nojsonl)
                    yield {
                        self.item_schema_name: item,
                        view_name_nojsonl: view,
                    }
                    # if schema contain a Conversation, add one
                    for entity_name, entity_schema_nojsonl in self.entities_schema.items():
                        if entity_schema_nojsonl is not None and is_conversation(entity_schema_nojsonl):
                            conversation = create_conversation(
                                id=shortuuid.uuid(),
                                kind="vqa",
                                item_id=item.id,
                            )
                            yield {"conversations": conversation}

                continue

            for i, dataset_piece in enumerate(dataset_pieces):
                dataset_piece = self._normalize_dataset_piece_keys(dict(dataset_piece))
                # Extract fps before item_metadata collection (Item has no fps field)
                fps = dataset_piece.pop("fps", None)
                frame_period_ms = 1000.0 / (fps if fps is not None else 24.0)

                item_metadata = {}
                for k in dataset_piece.keys():
                    if (
                        k not in self.views_schema
                        and k not in self.entities_schema
                        and k not in self.entity_dynamic_states_schema
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
                frame_views_by_stem: dict[str, tuple[str, View, int, float]] = {}
                for k, v in dataset_piece.items():
                    if k in self.views_schema:
                        view_name = k
                        view_schema = self.views_schema.get(view_name)
                        if view_schema is not None:
                            # Handle SequenceFrame views: expand glob patterns into individual frames
                            if is_sequence_frame(view_schema):
                                if isinstance(v, str) and any(c in v for c in ("*", "?", "[")):
                                    frame_files = sorted((self.source_dir / split.name).glob(v))
                                    if not frame_files:
                                        frame_files = sorted(self.source_dir.glob(v))
                                elif isinstance(v, list):
                                    frame_files = []
                                    for f in v:
                                        fp = self.source_dir / Path(f)
                                        if not fp.is_file():
                                            fp = self.source_dir / split.name / Path(f)
                                        if fp.is_file():
                                            frame_files.append(fp)
                                else:
                                    fp = self.source_dir / (
                                        Path(v) if split.name == Path(v).parts[0] else Path(split.name) / Path(v)
                                    )
                                    frame_files = [fp] if fp.is_file() else []

                                for idx, frame_file in enumerate(frame_files):
                                    if frame_file.suffix not in self.EXTENSIONS:
                                        continue
                                    timestamp = idx * frame_period_ms
                                    sf = self._create_view(
                                        item, frame_file, view_name, view_schema,
                                        timestamp=timestamp, frame_index=idx,
                                    )
                                    views_data.append((view_name, sf))
                                    frame_views_by_stem[frame_file.stem] = (view_name, sf, idx, timestamp)
                                continue

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
                                    view = self._create_view(item, view_file, view_name, view_schema)
                                    views_data.append((view_name, view))
                            else:
                                view_file = self.source_dir / (
                                    Path(v) if split.name == Path(v).parts[0] else Path(split.name) / Path(v)
                                )
                                if view_file.is_file() and view_file.suffix in self.EXTENSIONS:
                                    view = self._create_view(item, view_file, view_name, view_schema)
                                    views_data.append((view_name, view))

                all_entities_data: dict[str, list[Entity]] = defaultdict(list)
                all_entity_dynamic_states_data: dict[str, list[EntityDynamicState]] = defaultdict(list)
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

                # Process mask annotations (CompressedRLE) from file globs
                if frame_views_by_stem:
                    self._process_mask_annotations(
                        item, dataset_piece, split.name,
                        frame_views_by_stem,
                        all_entities_data,
                        all_entity_dynamic_states_data,
                        all_annotations_data,
                    )
                    self._process_bbox_track_annotations(
                        item, dataset_piece, split.name,
                        frame_views_by_stem, views_data,
                        all_entities_data,
                        all_entity_dynamic_states_data,
                        all_annotations_data,
                    )

                yield {self.item_schema_name: item}

                # Group SequenceFrame views by frame_index so each yielded dict
                # contains ALL camera views for a given frame (wide-format row).
                seq_frame_groups: dict[int, dict[str, View]] = defaultdict(dict)
                other_views: list[tuple[str, View]] = []

                for view_name, view in views_data:
                    if is_sequence_frame(type(view)):
                        seq_frame_groups[view.frame_index][view_name] = view
                    else:
                        other_views.append((view_name, view))

                # Yield non-SequenceFrame views individually
                for view_name, view in other_views:
                    yield {view_name: view}

                # Yield SequenceFrame views grouped by frame_index
                for frame_index in sorted(seq_frame_groups.keys()):
                    yield seq_frame_groups[frame_index]

                if all_entities_data is None:
                    continue

                yield all_entities_data
                yield all_entity_dynamic_states_data
                yield all_annotations_data

    def _create_item(self, **item_metadata) -> BaseSchema:
        return self.item_schema(**item_metadata)

    def _create_view(
        self, item: Item, view_file: Path, view_name: str, view_schema: type[View],
        timestamp: float = 0.0, frame_index: int = 0,
    ) -> View:
        if not issubclass(view_schema, View):
            raise ValueError("View schema must be a subclass of View")
        if view_schema not in _PIXANO_SCHEMA_REGISTRY.values():
            raise ValueError(
                f"View schema {view_schema} is not supported. You should implement your own _create_view method."
            )

        if self.embed_media:
            kwargs: dict = dict(
                id=view_file.stem if self.use_image_name_as_id else shortuuid.uuid(),
                item_id=item.id,
                view_name=view_name,
                blob=view_file.read_bytes(),
            )
        else:
            kwargs = dict(
                id=view_file.stem if self.use_image_name_as_id else shortuuid.uuid(),
                item_id=item.id,
                view_name=view_name,
                url=view_file,
                url_relative_path=self.media_dir,
            )
        if is_sequence_frame(view_schema):
            kwargs["timestamp"] = timestamp
            kwargs["frame_index"] = frame_index
        return create_instance_of_schema(view_schema, **kwargs)

    def _create_vqa_entities(
        self,
        item: Item,
        views_data: list[tuple[str, View]],
        entity_name: str,
        entity_schema: type[Entity],
        raw_entities_data: list[Any],
    ) -> tuple[dict[str, list[Entity]], dict[str, list[Annotation]]]:
        def update_view_target(
            content: str, view_rows: list[tuple[str, View]], default_target: tuple[str, View]
        ) -> tuple[str, View]:
            match = re.match(r".*<image (\d)>.*", content)  # TODO image_regex as parameter
            if match is None:
                return default_target
            for m in match.groups():
                num = int(m) - 1
                if num >= 0 and num < len(view_rows):
                    return view_rows[num]
            return default_target

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
            default_target = (view_name, view)

            conversation = entity_schema(
                id=shortuuid.uuid(),
                kind="vqa",
                item_id=item.id,
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

                target_view_name, target_view = update_view_target(content, views_data, default_target)
                target_frame_index = target_view.frame_index if hasattr(target_view, "frame_index") else -1

                query_msg = Message(
                    id=shortuuid.uuid(),
                    number=i,
                    type="QUESTION",
                    item_id=item.id,
                    entity_id=conversation.id,
                    source_id=self.source_id,
                    view_name=target_view_name,
                    frame_id=target_view.id,
                    frame_index=target_frame_index,
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
                        item_id=item.id,
                        entity_id=conversation.id,
                        source_id=self.source_id,
                        view_name=target_view_name,
                        frame_id=target_view.id,
                        frame_index=target_frame_index,
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

        # Resolve target view: use "view_name" if provided, otherwise fall back to first view.
        target_view_name = entities_data.pop("view_name", None) if isinstance(entities_data, dict) else None
        if target_view_name is not None:
            matched = [(n, v) for n, v in views_data if n == target_view_name]
            if not matched:
                raise ValueError(f"view_name '{target_view_name}' not found in views: {[n for n, _ in views_data]}")
            view_name, view = matched[0]
        else:
            view_name, view = views_data[0]
        frame_index = view.frame_index if hasattr(view, "frame_index") else -1

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
                            item_id=item.id,
                            view_name=view_name,
                            frame_id=view.id,
                            frame_index=frame_index,
                            entity_id=entity_id,
                            source_id=self.source_id,
                            **entities_data[attr][i],
                        )
                    else:
                        # TODO check jsonl format for mask & keypoints
                        if is_bbox(schema, True):
                            annotation = create_bbox(
                                id=shortuuid.uuid(),
                                item_id=item.id,
                                view_name=view_name,
                                frame_id=view.id,
                                frame_index=frame_index,
                                entity_id=entity_id,
                                source_id=self.source_id,
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
                    item_id=item.id,
                    **entity,
                )
            )

            for key, entity_annotation in entity_annotations.items():
                annotations[key].extend(entity_annotation)
        return entities, annotations

    def _resolve_tracking_entity_schema(self) -> tuple[str | None, type[Entity] | None]:
        """Resolve the entity schema used for auto-generated temporal objects."""
        candidates = [
            (name, schema)
            for name, schema in self.entities_schema.items()
            if not is_conversation(schema)
        ]
        if not candidates:
            return None, None

        preferred_names = ("objects", "entities", "entity")
        for preferred_name in preferred_names:
            for name, schema in candidates:
                if name == preferred_name:
                    return name, schema
        return candidates[0]

    def _resolve_entity_dynamic_state_schema(self) -> tuple[str | None, type[EntityDynamicState] | None]:
        """Resolve the dynamic state schema used for generated temporal states."""
        if not self.entity_dynamic_states_schema:
            return None, None

        preferred_names = ("states", "entity_dynamic_states", "entity_dynamic_state")
        for preferred_name in preferred_names:
            if preferred_name in self.entity_dynamic_states_schema:
                return preferred_name, self.entity_dynamic_states_schema[preferred_name]

        state_name = next(iter(self.entity_dynamic_states_schema))
        return state_name, self.entity_dynamic_states_schema[state_name]

    def _create_tracking_entity(
        self,
        item: Item,
        entity_schema: type[Entity],
        object_id: int,
        category: str = "",
    ) -> Entity:
        """Create one entity row for a tracked object ID."""
        kwargs: dict[str, Any] = {
            "id": shortuuid.uuid(),
            "item_id": item.id,
        }
        if "name" in entity_schema.model_fields:
            kwargs["name"] = f"object_{object_id}"
        if "category" in entity_schema.model_fields:
            kwargs["category"] = category or "object"
        return entity_schema(**kwargs)

    def _create_entity_dynamic_state(
        self,
        state_schema: type[EntityDynamicState],
        *,
        item_id: str,
        entity_id: str,
        tracklet_id: str,
        view_name: str,
        frame_id: str,
        frame_index: int,
    ) -> EntityDynamicState:
        """Create one dynamic state row linked to an entity/frame."""
        return state_schema(
            id=shortuuid.uuid(),
            item_id=item_id,
            entity_id=entity_id,
            tracklet_id=tracklet_id,
            source_id=self.source_id,
            view_name=view_name,
            frame_id=frame_id,
            frame_index=frame_index,
        )

    def _process_mask_annotations(
        self,
        item: Item,
        dataset_piece: dict,
        split_name: str,
        frame_views_by_stem: dict[str, tuple[str, View, int, float]],
        all_entities_data: dict[str, list[Entity]],
        all_entity_dynamic_states_data: dict[str, list[EntityDynamicState]],
        all_annotations_data: dict[str, list[Annotation]],
    ) -> None:
        """Process mask annotation keys (CompressedRLE) from file glob patterns.

        Reads mask PNGs with indexed pixel values (0=background, N=object_N),
        creates per-object binary masks, entities, optional dynamic states,
        and optional tracklets.
        """
        for annotation_key, annotation_schema in self.annotations_schema.items():
            if not is_compressed_rle(annotation_schema):
                continue

            raw_value = dataset_piece.get(annotation_key)
            if raw_value is None:
                continue

            # Only process glob patterns / file paths, not pre-built annotation data
            if not isinstance(raw_value, str):
                continue
            if not any(c in raw_value for c in ("*", "?", "[")):
                continue

            # Expand glob pattern to get mask files
            mask_files = sorted((self.source_dir / split_name).glob(raw_value))
            if not mask_files:
                mask_files = sorted(self.source_dir.glob(raw_value))
            if not mask_files:
                continue

            # Read all mask PNGs and discover unique object IDs
            frame_masks: list[tuple[np.ndarray, str, View, int, float]] = []
            all_object_ids: set[int] = set()

            for mask_file in mask_files:
                frame_info = frame_views_by_stem.get(mask_file.stem)
                if frame_info is None:
                    continue  # No matching frame for this mask
                view_name, view, frame_index, timestamp = frame_info

                mask_img = PIL.Image.open(mask_file)
                mask_array = np.array(mask_img)

                unique_ids = set(np.unique(mask_array).tolist())
                unique_ids.discard(0)  # Remove background
                all_object_ids.update(unique_ids)

                frame_masks.append((mask_array, view_name, view, frame_index, timestamp))

            if not all_object_ids:
                continue

            entity_name, entity_schema = self._resolve_tracking_entity_schema()
            state_name, state_schema = self._resolve_entity_dynamic_state_schema()
            has_tracklets = "tracklets" in self.annotations_schema

            # Create one entity per unique object ID.
            object_entities: dict[int, Entity] = {}
            for obj_id in sorted(all_object_ids):
                if entity_name is None or entity_schema is None:
                    break
                entity = self._create_tracking_entity(
                    item,
                    entity_schema=entity_schema,
                    object_id=obj_id,
                )
                all_entities_data[entity_name].append(entity)
                object_entities[obj_id] = entity

            object_tracklet_ids = {
                obj_id: shortuuid.uuid()
                for obj_id in sorted(all_object_ids)
                if has_tracklets and obj_id in object_entities
            }

            # Collect per-object frame appearances for tracklet creation
            object_appearances: dict[int, list[tuple[int, float]]] = defaultdict(list)

            # Create CompressedRLE masks per (object_id, frame)
            for mask_array, view_name, view, frame_index, timestamp in frame_masks:
                for obj_id in sorted(all_object_ids):
                    binary_mask = (mask_array == obj_id).astype(np.uint8)
                    if binary_mask.sum() == 0:
                        continue  # Object not present in this frame

                    object_appearances[obj_id].append((frame_index, timestamp))

                    entity = object_entities.get(obj_id)
                    entity_id = entity.id if entity else ""
                    tracklet_id = object_tracklet_ids.get(obj_id, "")
                    entity_dynamic_state_id = ""

                    if state_name is not None and state_schema is not None and entity is not None:
                        entity_dynamic_state = self._create_entity_dynamic_state(
                            state_schema,
                            item_id=item.id,
                            entity_id=entity.id,
                            tracklet_id=tracklet_id,
                            view_name=view_name,
                            frame_id=view.id,
                            frame_index=frame_index,
                        )
                        all_entity_dynamic_states_data[state_name].append(entity_dynamic_state)
                        entity_dynamic_state_id = entity_dynamic_state.id

                    rle = CompressedRLE.from_mask(
                        binary_mask,
                        id=shortuuid.uuid(),
                        item_id=item.id,
                        view_name=view_name,
                        frame_id=view.id,
                        frame_index=frame_index,
                        entity_id=entity_id,
                        source_id=self.source_id,
                        tracklet_id=tracklet_id,
                        entity_dynamic_state_id=entity_dynamic_state_id,
                    )
                    all_annotations_data[annotation_key].append(rle)

            # Create Tracklets
            if has_tracklets:
                seq_view_name = frame_masks[0][1]  # view_name shared by all frames
                for obj_id, appearances in object_appearances.items():
                    entity = object_entities.get(obj_id)
                    if entity is None:
                        continue
                    appearances.sort()
                    start_idx, start_ts = appearances[0]
                    end_idx, end_ts = appearances[-1]

                    tracklet = Tracklet(
                        id=object_tracklet_ids.get(obj_id, shortuuid.uuid()),
                        item_id=item.id,
                        view_name=seq_view_name,
                        entity_id=entity.id,
                        source_id=self.source_id,
                        start_frame=start_idx,
                        end_frame=end_idx,
                        start_timestamp=start_ts,
                        end_timestamp=end_ts,
                    )
                    all_annotations_data["tracklets"].append(tracklet)

    def _process_bbox_track_annotations(
        self,
        item: Item,
        dataset_piece: dict,
        split_name: str,
        frame_views_by_stem: dict[str, tuple[str, View, int, float]],
        views_data: list[tuple[str, View]],
        all_entities_data: dict[str, list[Entity]],
        all_entity_dynamic_states_data: dict[str, list[EntityDynamicState]],
        all_annotations_data: dict[str, list[Annotation]],
    ) -> None:
        """Process bbox track annotations from per-frame JSON files.

        Reads JSON files containing bounding boxes with track IDs, creates
        entities, BBox annotations per frame, optional dynamic states,
        and optional tracklet annotations.
        """
        for annotation_key, annotation_schema in self.annotations_schema.items():
            if not is_bbox(annotation_schema):
                continue

            raw_value = dataset_piece.get(annotation_key)
            if raw_value is None or not isinstance(raw_value, str):
                continue
            if not any(c in raw_value for c in ("*", "?", "[")):
                continue

            # Expand glob to get per-frame JSON files
            json_files = sorted((self.source_dir / split_name).glob(raw_value))
            if not json_files:
                json_files = sorted(self.source_dir.glob(raw_value))
            if not json_files:
                continue

            # Build view lookup: {view_name: {frame_index: (view_name, view)}}
            views_by_name_idx: dict[str, dict[int, tuple[str, View]]] = defaultdict(dict)
            for vname, view in views_data:
                if hasattr(view, "frame_index"):
                    views_by_name_idx[vname][view.frame_index] = (vname, view)

            # First pass: read all JSON files, collect unique (track_id, category) pairs
            file_data: list[tuple[str, dict]] = []  # (stem, parsed JSON)
            unique_tracks: dict[int, str] = {}  # track_id -> category

            for json_file in json_files:
                if json_file.suffix != ".json":
                    continue
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)
                file_data.append((json_file.stem, data))
                for obj in data.get("objects", []):
                    tid = obj.get("track_id")
                    if tid is not None:
                        unique_tracks.setdefault(tid, obj.get("category", ""))

            if not unique_tracks:
                continue

            entity_name, entity_schema = self._resolve_tracking_entity_schema()
            state_name, state_schema = self._resolve_entity_dynamic_state_schema()
            has_tracklets = "tracklets" in self.annotations_schema

            # Create one entity row per unique track_id.
            object_entities: dict[int, Entity] = {}
            if entity_name is not None and entity_schema is not None:
                for tid in sorted(unique_tracks.keys()):
                    entity = self._create_tracking_entity(
                        item,
                        entity_schema=entity_schema,
                        object_id=tid,
                        category=unique_tracks[tid],
                    )
                    all_entities_data[entity_name].append(entity)
                    object_entities[tid] = entity

            object_tracklet_ids = {
                tid: shortuuid.uuid()
                for tid in unique_tracks
                if has_tracklets and tid in object_entities
            }

            # Collect per-object frame appearances for tracklet creation
            object_appearances: dict[int, list[tuple[int, float]]] = defaultdict(list)

            # Second pass: create BBox annotations per frame
            for stem, data in file_data:
                frame_info = frame_views_by_stem.get(stem)
                if frame_info is None:
                    continue

                _view_name_default, _view_default, frame_index, timestamp = frame_info
                target_view_name = data.get("view_name")

                for obj in data.get("objects", []):
                    tid = obj.get("track_id")
                    coords = obj.get("bbox")
                    if tid is None or coords is None:
                        continue

                    # Resolve target view for this annotation
                    if target_view_name and target_view_name in views_by_name_idx:
                        frame_view = views_by_name_idx[target_view_name].get(frame_index)
                        if frame_view is not None:
                            target_view_name, target_view = frame_view
                        else:
                            target_view_name, target_view = _view_name_default, _view_default
                    else:
                        target_view_name, target_view = _view_name_default, _view_default

                    entity = object_entities.get(tid)
                    entity_id = entity.id if entity else ""
                    tracklet_id = object_tracklet_ids.get(tid, "")
                    entity_dynamic_state_id = ""

                    if state_name is not None and state_schema is not None and entity is not None:
                        entity_dynamic_state = self._create_entity_dynamic_state(
                            state_schema,
                            item_id=item.id,
                            entity_id=entity.id,
                            tracklet_id=tracklet_id,
                            view_name=target_view_name,
                            frame_id=target_view.id,
                            frame_index=frame_index,
                        )
                        all_entity_dynamic_states_data[state_name].append(entity_dynamic_state)
                        entity_dynamic_state_id = entity_dynamic_state.id

                    bbox = create_bbox(
                        id=shortuuid.uuid(),
                        coords=coords,
                        format="xywh",
                        is_normalized=all(0 <= x <= 1 for x in coords),
                        confidence=1.0,
                        item_id=item.id,
                        view_name=target_view_name,
                        frame_id=target_view.id,
                        frame_index=frame_index,
                        entity_id=entity_id,
                        source_id=self.source_id,
                        tracklet_id=tracklet_id,
                        entity_dynamic_state_id=entity_dynamic_state_id,
                    )
                    all_annotations_data[annotation_key].append(bbox)
                    object_appearances[tid].append((frame_index, timestamp))

            # Create Tracklets
            if has_tracklets:
                for tid, appearances in object_appearances.items():
                    entity = object_entities.get(tid)
                    if entity is None:
                        continue
                    appearances.sort()
                    start_idx, start_ts = appearances[0]
                    end_idx, end_ts = appearances[-1]

                    seq_view_name = file_data[0][1].get("view_name", _view_name_default) if file_data else _view_name_default

                    tracklet = Tracklet(
                        id=object_tracklet_ids.get(tid, shortuuid.uuid()),
                        item_id=item.id,
                        view_name=seq_view_name,
                        entity_id=entity.id,
                        source_id=self.source_id,
                        start_frame=start_idx,
                        end_frame=end_idx,
                        start_timestamp=start_ts,
                        end_timestamp=end_ts,
                    )
                    all_annotations_data["tracklets"].append(tracklet)

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

def extract_video_frames(
    video_path: Path, format: str = "JPEG", quality: int = 85
) -> Iterator[tuple[int, float, bytes]]:
    """Extract frames from a video as compressed image bytes.

    Args:
        video_path: Path to the video file.
        format: Output image format (e.g., "JPEG", "PNG").
        quality: JPEG quality (1-100). Only used for JPEG format.

    Yields:
        Tuples of (frame_index, timestamp_seconds, image_bytes).
    """
    import cv2

    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0  # fallback
    idx = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        encode_params = []
        if format.upper() == "JPEG":
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
        _, buffer = cv2.imencode(f".{format.lower()}", frame, encode_params)
        yield idx, idx / fps, buffer.tobytes()
        idx += 1
    cap.release()
