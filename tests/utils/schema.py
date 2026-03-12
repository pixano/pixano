from lancedb.pydantic import LanceModel


def register_schema(schema: type[LanceModel]) -> type[LanceModel]:
    """Compatibility helper for tests while schemas no longer require registration."""
    return schema
