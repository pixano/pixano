# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Models served by the local-mode inference: an embedding model, a detector and two segmenters, on CPU.

Mounted into the `pixano-inference` container by `docker-compose.inference.yml`, and passed to a
server started by hand (docs/running-by-hand.md). It lives in this repository, not in
pixano-inference, because it describes what *this* stack needs to be demonstrable on a machine
with no GPU — a deployment's own choice of models is its own file.

MobileCLIP2-S2 is small enough to run on CPU at a usable pace, about three images per second.
Its weights are fetched once on first load and cached in the inference's persistent volume.

YOLO26n is the smallest Ultralytics detector, trained on the 80 COCO classes. Ultralytics is
AGPL-3.0 (see docker-compose.inference.yml): a demonstration choice, which Pixano does not
depend on — nothing in Pixano names this model.

SAM 2.1 tiny and small turn what they are pointed at on an image, points or boxes, into masks:
two checkpoints, tiny the faster, small a second segmentation model beside it. Code and
checkpoints are Apache-2.0. Their weights come from huggingface.co on first load and are cached
under HF_HOME (the persistent volume in the container), not under PIXANO_INFERENCE_WEIGHTS_DIR.
Each replica holds about 1.5 GiB of memory, 2 GiB at peak. Every client of the server shares
these two deployments, the interactive smart-segment tool included.

Every model listed must load for the server to start. A missing plugin fails the list itself;
with strict startup, the server's default, so do weights that cannot be fetched or CPUs that
cannot be reserved.
"""

import os
from pathlib import Path

from pixano_inference.configs import DeploymentConfig, ModelConfig


# Ray reserves these for each model's one replica; two cores each keep a laptop responsive.
CLIP_CPUS = 2
YOLO_CPUS = 2

# Two CPUs for each SAM 2.1 replica: Ray gives a replica as many threads as it reserves CPUs for
# it, and a call's cost follows the thread count. Measured natively on macOS, on 2026-10-07 on an
# M1 Pro (8 cores, 16 GB) under other load: 1.6 to 2.0 s per image on one thread, 1.0 to 1.2 s on
# two, small 10 to 20 % slower than tiny. Measured on 2026-10-09 inside the compose's inference
# container (Docker Desktop on that machine, arm64, 8 CPUs; tiny, three boxes on a 224 × 224
# image): 10.7 s per call on one thread, about 6 s on two, 3.7 s on four; and through the server
# with one CPU each, 13 s for tiny and 14 s for small; with two each, 7 s and 7.8 s. Two each put
# the four models at all 8 CPUs the stack requires of Docker (CLIP 2 + YOLO 2 + SAM 2 × 2); four
# each would need 12. Ray's reservation is a count, not a pinning: the app, the worker and
# PostgreSQL still share the CPUs. A replica answers one call at a time, and a worker keeps at
# most its concurrency of them queued, 4 by default: in the container a queued call then waits at
# most about 4 × 7.8 s = 31 s, its own included, under the 60 s the server gives a segmentation
# call with its queue time.
SAM_CPUS = 2

# Sam2ImageModel's defaults, bfloat16 and torch.compile, are meant for a GPU. Compiling makes
# the first call slow, which on CPU risks the request timeout (pixano-inference's own Docker
# config turns it off too), and float32 is what SAM was measured with on CPU. No timeout_s
# either: segmentation keeps the server's default, 60 s per call with its queue time, above the
# longest wait a worker's calls make (above).
SAM_CPU_PARAMS = {"torch_dtype": "float32", "compile": False}

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
    # Tiny before small: the new UI's smart-segment tool takes the first segmentation model the
    # server lists, and tiny is the faster of the two.
    ModelConfig(
        name="sam2.1-tiny",
        model_class="Sam2ImageModel",
        model_params={"path": "facebook/sam2.1-hiera-tiny", **SAM_CPU_PARAMS},
        deployment=DeploymentConfig(num_gpus=0, num_cpus=SAM_CPUS, min_replicas=1, max_replicas=1),
    ),
    ModelConfig(
        name="sam2.1-small",
        model_class="Sam2ImageModel",
        model_params={"path": "facebook/sam2.1-hiera-small", **SAM_CPU_PARAMS},
        deployment=DeploymentConfig(num_gpus=0, num_cpus=SAM_CPUS, min_replicas=1, max_replicas=1),
    ),
]
