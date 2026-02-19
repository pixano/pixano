# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import os

from pixano.features import Text, create_text, is_text
from pixano.features.types.schema_reference import ItemRef, ViewRef
from tests.features.utils import make_tests_is_sublass_strict


def test_is_text():
    make_tests_is_sublass_strict(is_text, Text)


def test_create_text():
    # Test 1: dummy content and default references
    text = create_text(
        content="My taylor is rich!",
    )

    assert isinstance(text, Text)
    assert text.content == "My taylor is rich!"
    assert text.id == ""
    assert text.item_ref == ItemRef.none()
    assert text.parent_ref == ViewRef.none()

    # Test 2: dummy content and custom references
    text = create_text(
        content="My taylor is rich!",
        id="txt_1",
        item_ref=ItemRef(id="item_id"),
        parent_ref=ViewRef(id="view_id", name="view"),
    )
    assert isinstance(text, Text)
    assert text.content == "My taylor is rich!"
    assert text.id == "txt_1"
    assert text.item_ref == ItemRef(id="item_id")
    assert text.parent_ref == ViewRef(id="view_id", name="view")

    # Test 3: dummy content read from temp file
    import tempfile

    _, raw_text_file = tempfile.mkstemp(".txt")
    with open(raw_text_file, "w") as f:
        f.write("My taylor is rich!")

    text = create_text(
        content=None,
        url=raw_text_file,
        id="txt_2",
    )
    assert isinstance(text, Text)
    assert text.content == "My taylor is rich!"
    assert text.id == "txt_2"

    try:
        os.remove(raw_text_file)
    except Exception as err:
        print(f"Could not remove temp file {raw_text_file} : {err}")
        pass
