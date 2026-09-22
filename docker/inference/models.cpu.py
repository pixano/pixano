# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Models served by the local-mode inference: an embedding model, on CPU.

Mounted into the `pixano-inference` container by `docker-compose.inference.yml`. It lives in
this repository, not in pixano-inference, because it describes what *this* stack needs to be
demonstrable on a machine with no GPU — a deployment's own choice of models is its own file.

MobileCLIP2-S2 is small enough to run on CPU at a usable pace, about three images per second.
Its weights are fetched once on first load and cached in the inference's persistent volume.
"""

from pixano_inference.configs import DeploymentConfig, ModelConfig


# Ray reserves these for the model's one replica; two cores keep a laptop responsive.
CLIP_CPUS = 2

models = [
    ModelConfig(
        name="clip",
        model_class="OpenClipEmbeddingModel",
        model_params={"path": "MobileCLIP2-S2", "pretrained": "dfndr2b", "compile": False},
        deployment=DeploymentConfig(num_gpus=0, num_cpus=CLIP_CPUS, min_replicas=1, max_replicas=1),
    ),
]
