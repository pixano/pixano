# @Copyright: CEA-LIST/DIASI/SIALV/LVA (2023)
# @Author: CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
# @License: CECILL-C
#
# This software is a collaborative computer program whose purpose is to
# generate and explore labeled data for computer vision applications.
# This software is governed by the CeCILL-C license under French law and
# abiding by the rules of distribution of free software. You can use,
# modify and/ or redistribute the software under the terms of the CeCILL-C
# license as circulated by CEA, CNRS and INRIA at the following URL
#
# http://www.cecill.info

from pixano.data import (
    DatasetInfo,
    DatasetItem,
    DatasetStat,
    ItemBBox,
    ItemEmbedding,
    ItemFeature,
    ItemObject,
    ItemView,
)

# Example Datasets
datasets = {
    "db1": DatasetInfo(
        id="db1",
        name="db1",
        description="A dataset from my cool project",
        stats=[
            DatasetStat(
                name="Some numerical statistics",
                type="numerical",
                histogram=[
                    {"bin_start": 0.0, "bin_end": 1.0, "counts": 2, "split": "train"},
                    {"bin_start": 1.0, "bin_end": 2.0, "counts": 4, "split": "train"},
                    {"bin_start": 2.0, "bin_end": 3.0, "counts": 6, "split": "train"},
                    {"bin_start": 3.0, "bin_end": 4.0, "counts": 8, "split": "train"},
                ],
                range=[0.0, 10.0],
            ),
            DatasetStat(
                name="Some categorical statistics",
                type="categorical",
                histogram=[
                    {"Some categorical statistics": "a", "counts": 2, "split": "train"},
                    {"Some categorical statistics": "b", "counts": 4, "split": "train"},
                    {"Some categorical statistics": "c", "counts": 6, "split": "train"},
                    {"Some categorical statistics": "d", "counts": 8, "split": "train"},
                ],
            ),
        ],
    ),
    "db2": DatasetInfo(
        id="db2",
        name="db2",
        description="A dataset from my cool project",
        stats=[
            DatasetStat(
                name="Some numerical statistics",
                type="numerical",
                histogram=[
                    {"bin_start": 0.0, "bin_end": 1.0, "counts": 2, "split": "train"},
                    {"bin_start": 1.0, "bin_end": 2.0, "counts": 4, "split": "train"},
                    {"bin_start": 2.0, "bin_end": 3.0, "counts": 6, "split": "train"},
                    {"bin_start": 3.0, "bin_end": 4.0, "counts": 8, "split": "train"},
                ],
                range=[0.0, 10.0],
            ),
            DatasetStat(
                name="Some categorical statistics",
                type="categorical",
                histogram=[
                    {"Some categorical statistics": "a", "counts": 2, "split": "train"},
                    {"Some categorical statistics": "b", "counts": 4, "split": "train"},
                    {"Some categorical statistics": "c", "counts": 6, "split": "train"},
                    {"Some categorical statistics": "d", "counts": 8, "split": "train"},
                ],
            ),
        ],
    ),
}


# Example DatasetItems
items = {
    "db1": {
        "item1": DatasetItem(
            id="item1",
            image=[
                ItemView(
                    id="view1",
                    uri="http://example.com/image1.jpg",
                    features=[
                        ItemFeature(name="width", dtype="number", value=100),
                        ItemFeature(name="height", dtype="number", value=100),
                    ],
                )
            ],
            video=[
                ItemView(
                    id="view2",
                    uri="http://example.com/image2.jpg",
                    features=[
                        ItemFeature(name="width", dtype="number", value=100),
                        ItemFeature(name="height", dtype="number", value=100),
                    ],
                )
            ],
            objects=[
                ItemObject(
                    id="object1",
                    item_id="item1",
                    view_id="view1",
                    source_id="Ground Truth",
                    bbox=ItemBBox(
                        coords=[10, 10, 20, 20], format="xywh", confidence=0.9
                    ),
                    features=[
                        ItemFeature(name="color", dtype="string", value="red"),
                        ItemFeature(name="speed", dtype="number", value=50),
                    ],
                ),
                ItemObject(
                    id="object2",
                    item_id="item1",
                    view_id="view2",
                    source_id="Ground Truth",
                    bbox=ItemBBox(
                        coords=[30, 30, 10, 10], format="xywh", confidence=0.9
                    ),
                    features=[
                        ItemFeature(name="color", dtype="string", value="red"),
                        ItemFeature(name="speed", dtype="number", value=50),
                    ],
                ),
            ],
        ),
        "item2": DatasetItem(
            id="item2",
            image=[
                ItemView(
                    id="view1",
                    uri="http://example.com/image1.jpg",
                    features=[
                        ItemFeature(name="width", dtype="number", value=100),
                        ItemFeature(name="height", dtype="number", value=100),
                    ],
                )
            ],
            video=[
                ItemView(
                    id="view2",
                    uri="http://example.com/image2.jpg",
                    features=[
                        ItemFeature(name="width", dtype="number", value=100),
                        ItemFeature(name="height", dtype="number", value=100),
                    ],
                )
            ],
            objects=[
                ItemObject(
                    id="object1",
                    item_id="item2",
                    view_id="view1",
                    source_id="Ground Truth",
                    bbox=ItemBBox(
                        coords=[10, 10, 20, 20], format="xywh", confidence=0.9
                    ),
                    features=[
                        ItemFeature(name="color", dtype="string", value="red"),
                        ItemFeature(name="speed", dtype="number", value=50),
                    ],
                ),
                ItemObject(
                    id="object2",
                    item_id="item2",
                    view_id="view2",
                    source_id="Ground Truth",
                    bbox=ItemBBox(
                        coords=[30, 30, 10, 10], format="xywh", confidence=0.9
                    ),
                    features=[
                        ItemFeature(name="color", dtype="string", value="red"),
                        ItemFeature(name="speed", dtype="number", value=50),
                    ],
                ),
            ],
        ),
    },
    "db2": {
        "item3": DatasetItem(
            id="item3",
            image=[
                ItemView(
                    id="view1",
                    uri="http://example.com/image1.jpg",
                    features=[
                        ItemFeature(name="width", dtype="number", value=100),
                        ItemFeature(name="height", dtype="number", value=100),
                    ],
                )
            ],
            video=[
                ItemView(
                    id="view2",
                    uri="http://example.com/image2.jpg",
                    features=[
                        ItemFeature(name="width", dtype="number", value=100),
                        ItemFeature(name="height", dtype="number", value=100),
                    ],
                )
            ],
            objects=[
                ItemObject(
                    id="object1",
                    item_id="item1",
                    view_id="view1",
                    source_id="Ground Truth",
                    bbox=ItemBBox(
                        coords=[10, 10, 20, 20], format="xywh", confidence=0.9
                    ),
                    features=[
                        ItemFeature(name="color", dtype="string", value="red"),
                        ItemFeature(name="speed", dtype="number", value=50),
                    ],
                ),
                ItemObject(
                    id="object2",
                    item_id="item1",
                    view_id="view2",
                    source_id="Ground Truth",
                    bbox=ItemBBox(
                        coords=[30, 30, 10, 10], format="xywh", confidence=0.9
                    ),
                    features=[
                        ItemFeature(name="color", dtype="string", value="red"),
                        ItemFeature(name="speed", dtype="number", value=50),
                    ],
                ),
            ],
        ),
        "item4": DatasetItem(
            id="item4",
            image=[
                ItemView(
                    id="view1",
                    uri="http://example.com/image1.jpg",
                    features=[
                        ItemFeature(name="width", dtype="number", value=100),
                        ItemFeature(name="height", dtype="number", value=100),
                    ],
                )
            ],
            video=[
                ItemView(
                    id="view2",
                    uri="http://example.com/image2.jpg",
                    features=[
                        ItemFeature(name="width", dtype="number", value=100),
                        ItemFeature(name="height", dtype="number", value=100),
                    ],
                )
            ],
            objects=[
                ItemObject(
                    id="object1",
                    item_id="item2",
                    view_id="view1",
                    source_id="Ground Truth",
                    bbox=ItemBBox(
                        coords=[10, 10, 20, 20], format="xywh", confidence=0.9
                    ),
                    features=[
                        ItemFeature(name="color", dtype="string", value="red"),
                        ItemFeature(name="speed", dtype="number", value=50),
                    ],
                ),
                ItemObject(
                    id="object2",
                    item_id="item2",
                    view_id="view2",
                    source_id="Ground Truth",
                    bbox=ItemBBox(
                        coords=[30, 30, 10, 10], format="xywh", confidence=0.9
                    ),
                    features=[
                        ItemFeature(name="color", dtype="string", value="red"),
                        ItemFeature(name="speed", dtype="number", value=50),
                    ],
                ),
            ],
        ),
    },
}

# Example ItemEmbeddings
item_embeddings = {
    "db1": {
        "SAM": {
            "item1": [
                ItemEmbedding(view_id="view1", data="b64 string item1 SAM"),
                ItemEmbedding(view_id="view2", data="b64 string item1 SAM"),
            ],
            "item2": [
                ItemEmbedding(view_id="view1", data="b64 string item2 SAM"),
                ItemEmbedding(view_id="view2", data="b64 string item2 SAM"),
            ],
        },
        "CLIP": {
            "item1": [
                ItemEmbedding(view_id="view1", data="b64 string item1 CLIP"),
                ItemEmbedding(view_id="view2", data="b64 string item1 CLIP"),
            ],
            "item2": [
                ItemEmbedding(view_id="view1", data="b64 string item2 CLIP"),
                ItemEmbedding(view_id="view2", data="b64 string item2 CLIP"),
            ],
        },
    },
    "db2": {
        "SAM": {
            "item3": [
                ItemEmbedding(view_id="view1", data="b64 string item3 SAM"),
                ItemEmbedding(view_id="view2", data="b64 string item3 SAM"),
            ],
            "item4": [
                ItemEmbedding(view_id="view1", data="b64 string item4 SAM"),
                ItemEmbedding(view_id="view2", data="b64 string item4 SAM"),
            ],
        },
        "CLIP": {
            "item3": [
                ItemEmbedding(view_id="view1", data="b64 string item3 CLIP"),
                ItemEmbedding(view_id="view2", data="b64 string item3 CLIP"),
            ],
            "item4": [
                ItemEmbedding(view_id="view1", data="b64 string item4 CLIP"),
                ItemEmbedding(view_id="view2", data="b64 string item4 CLIP"),
            ],
        },
    },
}

# Example models
models = ["sam_vit_b_01ec64.onnx", "sam_vit_h_4b8939.onnx"]
