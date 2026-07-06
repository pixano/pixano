# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Pixano JSONL v2 — the canonical, hand-authorable annotation format (spec §5)."""

from .importer import PIXANO_JSONL, PixanoJsonlImporter
from .parser import ParsedLine, parse_file, view_kinds_of
from .spec import (
    HEADER_KEY,
    RESERVED_KINDS,
    ConversationSpec,
    EntitySpec,
    HeaderDefaults,
    HeaderLine,
    LineModel,
    MessageSpec,
    SidecarSpec,
)


__all__ = [
    "HEADER_KEY",
    "RESERVED_KINDS",
    "ConversationSpec",
    "EntitySpec",
    "HeaderDefaults",
    "HeaderLine",
    "LineModel",
    "MessageSpec",
    "PIXANO_JSONL",
    "ParsedLine",
    "PixanoJsonlImporter",
    "SidecarSpec",
    "parse_file",
    "view_kinds_of",
]
