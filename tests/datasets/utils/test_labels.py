# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.utils.labels import (
    coco_ids_80to91,
    coco_names_80,
    coco_names_91,
    dota_ids,
    voc_names,
)


def test_coco_ids_80to91():
    for i in range(1, 80):
        assert isinstance(coco_ids_80to91(i), int)

def test_coco_names_80():
    for i in range(1, 80):
        assert isinstance(coco_names_80(i), str)

def test_coco_names_91():
    for i in range(1, 91):
        assert isinstance(coco_names_91(i), str)

def test_dota_ids():
    dota_labels = [
        "plane",
        "ship",
        "storage tank",
        "baseball diamond",
        "tennis court",
        "basketball court",
        "ground track field",
        "harbor",
        "bridge",
        "large vehicle",
        "small vehicle",
        "helicopter",
        "roundabout",
        "soccer ball field",
        "swimming pool",
        "container crane",
        "airport",
        "helipad",
    ]
    for label in dota_labels:
        assert isinstance(dota_ids(label), int)

def test_voc_names():
    for i in range(1, 20):
        assert isinstance(voc_names(i), str)
