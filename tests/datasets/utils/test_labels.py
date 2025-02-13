# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.utils.labels import CATEGORY_IDS, CATEGORY_NAMES, category_id, category_name, coco_ids_80to91


def test_coco_ids_80to91():
    for i in range(1, 80):
        assert isinstance(coco_ids_80to91(i), int)


def test_category_name():
    for format_name, format in CATEGORY_NAMES.items():
        for cat_id, cat_name in format.items():
            assert category_name(cat_id, format_name) == cat_name


def test_category_id():
    for format_name, format in CATEGORY_IDS.items():
        for cat_name, cat_id in format.items():
            assert category_id(cat_name, format_name) == cat_id
