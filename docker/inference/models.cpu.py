# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Models served by the local-mode inference: an embedding model and a detector, on CPU.

Mounted into the `pixano-inference` container by `docker-compose.inference.yml`. It lives in
this repository, not in pixano-inference, because it describes what *this* stack needs to be
demonstrable on a machine with no GPU — a deployment's own choice of models is its own file.

MobileCLIP2-S2 is small enough to run on CPU at a usable pace, about three images per second.
Its weights are fetched once on first load and cached in the inference's persistent volume.

YOLO26n is the smallest Ultralytics detector, trained on the 80 COCO classes. Ultralytics is
AGPL-3.0 (see dockerfiles/Dockerfile.inference-local): a demonstration choice, which Pixano
does not depend on — the job form offers whatever detection model the inference serves.
"""

import os
from pathlib import Path

from pixano_inference.configs import DeploymentConfig, ModelConfig


# Ray reserves these for each model's one replica; two cores each keep a laptop responsive.
CLIP_CPUS = 2
YOLO_CPUS = 2

# Where YOLO fetches its weights on first load, and finds them afterwards. In the container,
# the inference's persistent volume; run by hand, any writable directory.
WEIGHTS_DIR = Path(os.environ.get("PIXANO_INFERENCE_WEIGHTS_DIR", "/data"))

models = [
    ModelConfig(
        name="clip",
        model_class="OpenClipEmbeddingModel",
        model_params={"path": "MobileCLIP2-S2", "pretrained": "dfndr2b", "compile": False},
        deployment=DeploymentConfig(num_gpus=0, num_cpus=CLIP_CPUS, min_replicas=1, max_replicas=1),
    ),
    ModelConfig(
        name="yolo26n",
        model_class="YOLOModel",
        model_params={"path": str(WEIGHTS_DIR / "yolo" / "yolo26n.pt")},
        deployment=DeploymentConfig(num_gpus=0, num_cpus=YOLO_CPUS, min_replicas=1, max_replicas=1),
    ),
]
