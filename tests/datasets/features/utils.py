# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Callable


def make_tests_is_sublass_strict(is_fn: Callable, cls: type):
    # Test 1: is instance
    assert is_fn(cls)

    # Test 2: not instance
    assert not is_fn(type(1))

    class DummySubclass(cls):
        pass

    # Test 3: subclass
    assert is_fn(DummySubclass, strict=False)

    # Test 4: subclass with strict mode
    assert not is_fn(DummySubclass, strict=True)
