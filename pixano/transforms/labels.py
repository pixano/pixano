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


def coco_names_80(label: int) -> str:
    """Return COCO category name (80 classes)

    Args:
        label (int): Category ID

    Returns:
        name (str): Category name
    """

    coco_dict = {
        1: "person",
        2: "bicycle",
        3: "car",
        4: "motorcycle",
        5: "airplane",
        6: "bus",
        7: "train",
        8: "truck",
        9: "boat",
        10: "traffic light",
        11: "fire hydrant",
        12: "stop sign",
        13: "parking meter",
        14: "bench",
        15: "bird",
        16: "cat",
        17: "dog",
        18: "horse",
        19: "sheep",
        20: "cow",
        21: "elephant",
        22: "bear",
        23: "zebra",
        24: "giraffe",
        25: "backpack",
        26: "umbrella",
        27: "handbag",
        28: "tie",
        29: "suitcase",
        30: "frisbee",
        31: "skis",
        32: "snowboard",
        33: "sports ball",
        34: "kite",
        35: "baseball bat",
        36: "baseball glove",
        37: "skateboard",
        38: "surfboard",
        39: "tennis racket",
        40: "bottle",
        41: "wine glass",
        42: "cup",
        43: "fork",
        44: "knife",
        45: "spoon",
        46: "bowl",
        47: "banana",
        48: "apple",
        49: "sandwich",
        50: "orange",
        51: "broccoli",
        52: "carrot",
        53: "hot dog",
        54: "pizza",
        55: "donut",
        56: "cake",
        57: "chair",
        58: "couch",
        59: "potted plant",
        60: "bed",
        61: "dining table",
        62: "toilet",
        63: "tv",
        64: "laptop",
        65: "mouse",
        66: "remote",
        67: "keyboard",
        68: "cell phone",
        69: "microwave",
        70: "oven",
        71: "toaster",
        72: "sink",
        73: "refrigerator",
        74: "book",
        75: "clock",
        76: "vase",
        77: "scissors",
        78: "teddy bear",
        79: "hair drier",
        80: "toothbrush",
    }

    return coco_dict[int(label)]


def coco_names_91(label: int) -> str:
    """Return COCO category name (91 classes)

    Args:
        label (int): Category ID

    Returns:
        name (str): Category name
    """

    coco_dict = {
        1: "person",
        2: "bicycle",
        3: "car",
        4: "motorbike",
        5: "aeroplane",
        6: "bus",
        7: "train",
        8: "truck",
        9: "boat",
        10: "trafficlight",
        11: "firehydrant",
        12: "streetsign",
        13: "stopsign",
        14: "parkingmeter",
        15: "bench",
        16: "bird",
        17: "cat",
        18: "dog",
        19: "horse",
        20: "sheep",
        21: "cow",
        22: "elephant",
        23: "bear",
        24: "zebra",
        25: "giraffe",
        26: "hat",
        27: "backpack",
        28: "umbrella",
        29: "shoe",
        30: "eyeglasses",
        31: "handbag",
        32: "tie",
        33: "suitcase",
        34: "frisbee",
        35: "skis",
        36: "snowboard",
        37: "sportsball",
        38: "kite",
        39: "baseballbat",
        40: "baseballglove",
        41: "skateboard",
        42: "surfboard",
        43: "tennisracket",
        44: "bottle",
        45: "plate",
        46: "wineglass",
        47: "cup",
        48: "fork",
        49: "knife",
        50: "spoon",
        51: "bowl",
        52: "banana",
        53: "apple",
        54: "sandwich",
        55: "orange",
        56: "broccoli",
        57: "carrot",
        58: "hotdog",
        59: "pizza",
        60: "donut",
        61: "cake",
        62: "chair",
        63: "sofa",
        64: "pottedplant",
        65: "bed",
        66: "mirror",
        67: "diningtable",
        68: "window",
        69: "desk",
        70: "toilet",
        71: "door",
        72: "tvmonitor",
        73: "laptop",
        74: "mouse",
        75: "remote",
        76: "keyboard",
        77: "cellphone",
        78: "microwave",
        79: "oven",
        80: "toaster",
        81: "sink",
        82: "refrigerator",
        83: "blender",
        84: "book",
        85: "clock",
        86: "vase",
        87: "scissors",
        88: "teddybear",
        89: "hairdrier",
        90: "toothbrush",
        91: "hairbrush",
    }

    return coco_dict[int(label)]


def voc_names(label: int) -> str:
    """Return VOC category name (20 classes)

    Args:
        label (int): Category ID

    Returns:
        name (str): Category name
    """

    voc_dict = {
        1: "aeroplane",
        2: "bicycle",
        3: "bird",
        4: "boat",
        5: "bottle",
        6: "bus",
        7: "car",
        8: "cat",
        9: "chair",
        10: "cow",
        11: "dining table",
        12: "dog",
        13: "horse",
        14: "motorbike",
        15: "person",
        16: "potted plant",
        17: "sheep",
        18: "sofa",
        19: "train",
        20: "tv / monitor",
    }

    return voc_dict[int(label)]
