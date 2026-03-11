"""Generic resource routers."""

from typing import Any

from fastapi import APIRouter, Depends

from pixano.api.models import PaginatedResponse
from pixano.api.resources import ResourceSpec
from pixano.api.routers._deps import FilterParams, PaginationParams, get_dataset_dep
from pixano.api.service import BaseService
from pixano.datasets import Dataset


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
        response_model=PaginatedResponse[response_model],
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
            body: create_model,
            dataset: Dataset = Depends(get_dataset_dep),
        ) -> Any:
            """Create a resource from the request body."""

            service = BaseService(dataset, resource)
            return service.create(body.model_dump())

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
            body: update_model,
            dataset: Dataset = Depends(get_dataset_dep),
        ) -> Any:
            """Update a resource by id."""

            service = BaseService(dataset, resource)
            return service.update(id, body.model_dump(exclude_unset=True))

    if resource.allow_delete:

        @router.delete(
            "/{id}",
            status_code=204,
            operation_id=f"delete_{resource.name}",
            summary=f"Delete a {resource.name}",
            description=f"Delete a single {resource.name} by id.",
        )
        def delete_resource(
            id: str,
            dataset: Dataset = Depends(get_dataset_dep),
        ) -> None:
            """Delete a resource by id."""

            service = BaseService(dataset, resource)
            service.delete(id)

    return router


__all__ = ["create_resource_router"]
