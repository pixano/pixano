# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

import pyarrow.json as pa_json
import shortuuid

from pixano.datasets.dataset_schema import DatasetItem
from pixano.datasets.utils import mosaic
from pixano.datasets.workspaces import DefaultVQADatasetItem, WorkspaceType
from pixano.features import BaseSchema, Entity, Item, Message, View, is_conversation
from pixano.features.schemas.annotations import Annotation
from pixano.features.schemas.registry import _PIXANO_SCHEMA_REGISTRY
from pixano.features.schemas.source import SourceKind
from pixano.features.types.schema_reference import EntityRef, ItemRef, SourceRef, ViewRef
from pixano.features.utils.creators import create_instance_of_schema

from .image import ImageFolderBuilder


class VQAFolderBuilder(ImageFolderBuilder):
    """Builder for vqa datasets stored in a folder."""

    WORKSPACE_TYPE = WorkspaceType.IMAGE_VQA
    DEFAULT_SCHEMA: type[DatasetItem] = DefaultVQADatasetItem

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
                    dataset_pieces = self._read_annotations(split / self.METADATA_FILENAME)
                except Exception:
                    raise ValueError(f"Could not read annotation file {split / self.METADATA_FILENAME}")

                for dataset_piece in dataset_pieces:
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
                    item = self._create_item(split.name, **item_metadata)

                    views_data: list[tuple[str, View]] = []
                    all_entities_data: dict[str, list[Entity]] = defaultdict(list)
                    all_annotations_data: dict[str, list[Annotation]] = defaultdict(list)
                    for k, v in dataset_piece.items():
                        if k in self.views_schema:
                            view_name = k
                            s = self.views_schema.get(view_name)
                            if s is None:
                                raise ValueError("View schema must be defined in the schemas argument.")
                            view_schema: type[View] = s

                            # create views
                            if isinstance(v, list):
                                if len(v) > 1:
                                    # create a mosaic from item images
                                    mosaic_file = mosaic(self.source_dir, split.name, v, view_name)
                                    view_file = self.source_dir / mosaic_file
                                else:
                                    view_file = self.source_dir / Path(v[0])
                                    if not view_file.is_file():  # no split path in metadata.jsonl
                                        view_file = self.source_dir / split / Path(v[0])
                                if view_file.is_file() and view_file.suffix in self.EXTENSIONS:
                                    view = self._create_vqa_view(item, view_file, view_schema)
                                    views_data.append((view_name, view))

                    for k, v in dataset_piece.items():
                        if k in self.entities_schema:
                            if source_id is None:
                                source_id = self.add_source("Builder", SourceKind.OTHER)
                            entity_name = k
                            raw_entities_data = v

                            # create entities and their annotations
                            entities_data, annotations_data = self._create_vqa_entities(
                                item, views_data, entity_name, raw_entities_data, source_id
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

    def _create_vqa_view(self, item: Item, view_file: Path, view_schema: type[View]) -> View:
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

    def _create_vqa_entities(
        self,
        item: Item,
        views_data: list[tuple[str, View]],
        entity_name: str,
        raw_entities_data: list[Any],
        source_id: str,
    ) -> tuple[dict[str, list[Entity]], dict[str, list[Annotation]]]:
        def update_viewref(content, views_data, view_ref):
            match = re.match(r".*<image (\d)>.*", content)
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

        s = self.entities_schema.get(entity_name)
        if s is None:
            raise ValueError("Entity schema must be defined in the schemas argument.")
        entity_schema: type[Entity] = s

        default_user = "import"
        if is_conversation(entity_schema):
            entities_data: list[list[Any]] = []

            if isinstance(raw_entities_data, list):
                if all(isinstance(data, list) for data in raw_entities_data):
                    entities_data = raw_entities_data
                if all(isinstance(data, dict) for data in raw_entities_data):
                    entities_data = [raw_entities_data]

            for conv in entities_data:
                view_name, view = views_data[0]
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
                        source_ref=SourceRef(id=source_id),
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
                            source_ref=SourceRef(id=source_id),
                            timestamp=datetime.now(),
                            **response,
                        )
                        annotations["messages"].append(response_msg)

        else:  # classic entity
            pass

        return entities, annotations

    def _read_annotations(self, annotations_file: Path) -> list[dict]:
        if not annotations_file.exists():
            raise FileNotFoundError(f"Anotations file {annotations_file} not found")
        return pa_json.read_json(annotations_file).to_pylist()
