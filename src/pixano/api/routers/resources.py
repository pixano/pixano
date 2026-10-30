# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Generic resource routers."""

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from pixano.api.models import ConditionalDeleteResponse, PaginatedResponse
from pixano.api.resources import ResourceSpec
from pixano.api.routers._deps import FilterParams, PaginationParams, get_dataset_dep
from pixano.api.service import BaseService
from pixano.datasets import Dataset
from pixano.schemas import SchemaGroup


def _list_kwargs(resource: ResourceSpec, filters: FilterParams, pagination: PaginationParams) -> dict[str, Any]:
    kwargs = {name: getattr(filters, name) for name in resource.list_filters}
    kwargs["limit"] = pagination.limit
    kwargs["offset"] = pagination.offset
    return kwargs


def create_resource_router(resource: ResourceSpec) -> APIRouter:
    """Build one CRUD router from a static resource definition."""
    router = APIRouter(prefix=f"/datasets/{{dataset_id}}/{resource.path}", tags=[resource.tag])
    response_model = resource.response_model

    @router.get(
        "",
        response_model=PaginatedResponse[response_model],  # type: ignore[valid-type]
        operation_id=f"list_{resource.path.replace('-', '_')}",
        summary=f"List {resource.tag.lower()}",
        description=f"List {resource.tag.lower()} in a dataset with optional filters and pagination.",
    )
    def list_resource(
        dataset: Dataset = Depends(get_dataset_dep),
        pagination: PaginationParams = Depends(),
        filters: FilterParams = Depends(),
    ) -> Any:
        """Return a paginated collection of resources."""
        service = BaseService(dataset, resource)
        return service.list(**_list_kwargs(resource, filters, pagination))

    @router.get(
        "/{id}",
        response_model=response_model,
        operation_id=f"get_{resource.name}",
        summary=f"Get a {resource.name}",
        description=f"Fetch a single {resource.name} by id.",
    )
    def get_resource(
        id: str,
        dataset: Dataset = Depends(get_dataset_dep),
    ) -> Any:
        """Return one resource by id."""
        service = BaseService(dataset, resource)
        return service.get(id)

    if resource.create_model is not None and resource.allow_create:
        create_model = resource.create_model

        @router.post(
            "",
            response_model=response_model,
            status_code=201,
            operation_id=f"create_{resource.name}",
            summary=f"Create a {resource.name}",
            description=f"Create a new {resource.name} row in the dataset.",
        )
        def create_resource(
            body: create_model,  # type: ignore[valid-type]
            dataset: Dataset = Depends(get_dataset_dep),
        ) -> Any:
            """Create a resource from the request body."""
            service = BaseService(dataset, resource)
            return service.create(body.model_dump())  # type: ignore[attr-defined]

    if resource.update_model is not None and resource.allow_update:
        update_model = resource.update_model

        @router.put(
            "/{id}",
            response_model=response_model,
            operation_id=f"replace_{resource.name}",
            summary=f"Update a {resource.name}",
            description=f"Replace mutable fields on an existing {resource.name}.",
        )
        def update_resource(
            id: str,
            body: update_model,  # type: ignore[valid-type]
            prune_orphan_entity: bool = False,
            dataset: Dataset = Depends(get_dataset_dep),
        ) -> Any:
            """Update a resource by id.

            When ``prune_orphan_entity`` is set and an annotation's ``entity_id``
            changes, the previously attached entity is deleted if no stored row
            names it any more (an annotation of any table, a child entity, a
            dynamic state). Off by default so plain PUT semantics are unchanged.
            """
            service = BaseService(dataset, resource)
            payload = body.model_dump(exclude_unset=True)  # type: ignore[attr-defined]
            return service.update(id, payload, prune_orphan_entity=prune_orphan_entity)

    if resource.allow_delete and resource.schema_group == SchemaGroup.ENTITY:
        _add_entity_delete_route(router, resource)
    elif resource.allow_delete:

        @router.delete(
            "/{id}",
            status_code=204,
            operation_id=f"delete_{resource.name}",
            summary=f"Delete a {resource.name}",
            description=f"Delete a single {resource.name} by id.",
        )
        def delete_resource(
            id: str,
            prune_orphan_entity: bool = False,
            dataset: Dataset = Depends(get_dataset_dep),
        ) -> None:
            """Delete a resource by id.

            When ``prune_orphan_entity`` is set and the resource is an annotation,
            its parent entity is also deleted if no stored row names it any more
            (an annotation of any table, a child entity, a dynamic state). Off by
            default so plain DELETE semantics are unchanged.
            """
            service = BaseService(dataset, resource)
            service.delete(id, prune_orphan_entity=prune_orphan_entity)

    return router


def _add_entity_delete_route(router: APIRouter, resource: ResourceSpec) -> None:
    """Add an entity resource's delete, which can be asked to spare an entity a row names."""

    @router.delete(
        "/{id}",
        status_code=204,
        response_model=None,
        operation_id=f"delete_{resource.name}",
        summary=f"Delete a {resource.name}",
        description=(
            f"Delete a single {resource.name} by id. With `only_if_unnamed=true`, delete it only when no "
            "annotation of any table, no child entity and no entity dynamic state names it, and answer "
            "200 with whether it was deleted."
        ),
        responses={200: {"model": ConditionalDeleteResponse, "description": "Asked with `only_if_unnamed`."}},
    )
    def delete_entity(
        id: str,
        only_if_unnamed: bool = False,
        dataset: Dataset = Depends(get_dataset_dep),
    ) -> JSONResponse | None:
        """Delete an entity by id, or only when no stored row names it.

        ``only_if_unnamed`` is for a client undoing an entity it created, such as the annotation
        interface: it cannot see every row that may name the entity. Without the parameter, the
        entity is deleted whatever names it, and the answer is a 204 as before.
        """
        service = BaseService(dataset, resource)
        if not only_if_unnamed:
            service.delete(id)
            return None
        deleted = service.delete_if_unnamed(id)
        return JSONResponse(status_code=200, content=ConditionalDeleteResponse(deleted=deleted).model_dump())


__all__ = ["create_resource_router"]
