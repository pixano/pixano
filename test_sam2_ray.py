# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""End-to-end SAM2 test runner for the Ray Serve API.

This script can either:

1. Start a local server from a Python config file, then run a segmentation
   request against it.
2. Connect to an already-running server and send the same requests.

It prints a JSON summary of the request and saves overlay images for the
best-scoring masks so you can inspect the result visually.

Examples:
    Start a local server from the default config and run the single-point test:

        uv run python scripts/test_sam2_ray.py

    Run the prompt batch used in the docs:

        uv run python scripts/test_sam2_ray.py --scenario docs-prompts

    Run a coarse box prompt over the truck image:

        uv run python scripts/test_sam2_ray.py --scenario box

    Connect to an existing server instead of starting one:

        uv run python scripts/test_sam2_ray.py \
            --no-start-server \
            --server-url http://127.0.0.1:7463

    Send a custom point prompt:

        uv run python scripts/test_sam2_ray.py \
            --point 300,375 \
            --label 1 \
            --single-mask
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import time
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from PIL import Image
from pixano_inference.client import PixanoInferenceClient
from pixano_inference.ray import InferenceServer
from pixano_inference.schemas import SegmentationRequest


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "deploy" / "sam2_example.py"
DEFAULT_IMAGE = ROOT / "docs" / "assets" / "examples" / "sam2" / "truck.jpg"
DEFAULT_OUTPUT_DIR = Path("/tmp/pixano-sam2-e2e")
DEFAULT_MODEL_NAME = "sam2-image"


def parse_point(value: str) -> list[int]:
    """Parse a point from 'x,y'."""
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 2:
        raise argparse.ArgumentTypeError(f"Invalid point '{value}'. Expected 'x,y'.")

    try:
        x, y = (int(part) for part in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid point '{value}'. Coordinates must be integers.") from exc

    return [x, y]


def parse_box(value: str) -> list[int]:
    """Parse a box from 'x1,y1,x2,y2'."""
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(f"Invalid box '{value}'. Expected 'x1,y1,x2,y2'.")

    try:
        x1, y1, x2, y2 = (int(part) for part in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid box '{value}'. Coordinates must be integers.") from exc

    return [x1, y1, x2, y2]


def image_to_data_url(image_path: Path) -> tuple[bytes, str]:
    """Read an image and encode it as a base64 data URL."""
    ext = image_path.suffix.lstrip(".").lower()
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}.get(ext, "png")
    image_bytes = image_path.read_bytes()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    return image_bytes, f"data:image/{mime};base64,{image_b64}"


def save_overlay(image_bytes: bytes, mask: np.ndarray, output_path: Path) -> None:
    """Save a red overlay of a binary mask on top of the input image."""
    image = Image.open(BytesIO(image_bytes)).convert("RGBA")
    array = np.array(image)
    array[mask.astype(bool), 0] = 255
    array[mask.astype(bool), 1] = (0.5 * array[mask.astype(bool), 1]).astype(np.uint8)
    array[mask.astype(bool), 2] = (0.5 * array[mask.astype(bool), 2]).astype(np.uint8)
    Image.fromarray(array, "RGBA").save(output_path)


def default_payload_for_scenario(scenario: str) -> dict[str, Any]:
    """Return the request payload used for the selected preset."""
    if scenario == "single-point":
        return {
            "points": [[[300, 375]]],
            "labels": [[1]],
            "multimask_output": False,
        }

    if scenario == "docs-prompts":
        return {
            "points": [[[300, 375]], [[500, 375], [3, 3]]],
            "labels": [[1], [1, 0]],
            "multimask_output": True,
        }

    if scenario == "box":
        return {
            "boxes": [[40, 180, 1120, 700]],
            "multimask_output": False,
        }

    raise ValueError(f"Unsupported scenario '{scenario}'.")


def build_request_payload(args: argparse.Namespace) -> dict[str, Any]:
    """Build the segmentation request payload from CLI arguments."""
    payload = default_payload_for_scenario(args.scenario)

    if args.point:
        labels = args.label if args.label else [1] * len(args.point)
        if len(labels) != len(args.point):
            raise ValueError("The number of --label values must match the number of --point values.")

        payload.pop("boxes", None)
        payload["points"] = [args.point]
        payload["labels"] = [labels]

    if args.box:
        payload.pop("points", None)
        payload.pop("labels", None)
        payload["boxes"] = [args.box]

    if args.multimask_output is not None:
        payload["multimask_output"] = args.multimask_output

    return payload


async def wait_until_ready(base_url: str, timeout_s: int) -> dict[str, Any]:
    """Poll the readiness endpoint until the server is available."""
    deadline = time.time() + timeout_s
    last_error: Exception | None = None

    while time.time() < deadline:
        try:
            response = httpx.get(f"{base_url}/ready", timeout=2.0)
            if response.status_code == 200:
                return response.json()
        except Exception as exc:
            last_error = exc

        await asyncio.sleep(1)

    if last_error is not None:
        raise RuntimeError(f"Server did not become ready: {last_error}") from last_error
    raise RuntimeError("Server did not become ready before the timeout expired.")


def summarize_masks(
    response,
    request_payload: dict[str, Any],
    image_bytes: bytes,
    output_dir: Path,
    scenario: str,
) -> list[dict[str, Any]]:
    """Summarize masks, scores, and prompt consistency for each request item."""
    output_dir.mkdir(parents=True, exist_ok=True)

    score_matrix = response.data.scores.to_numpy()
    prompt_points = request_payload.get("points", [])
    prompt_labels = request_payload.get("labels", [])
    prompt_boxes = request_payload.get("boxes", [])
    summaries: list[dict[str, Any]] = []

    for prompt_index, prompt_masks in enumerate(response.data.masks):
        scores = score_matrix[prompt_index]
        best_index = int(np.argmax(scores))
        best_mask = prompt_masks[best_index].to_mask().astype(np.uint8)
        ys, xs = np.where(best_mask > 0)

        bbox = None
        if len(xs) and len(ys):
            bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]

        overlay_path = output_dir / f"{scenario}_prompt_{prompt_index}_best.png"
        save_overlay(image_bytes, best_mask, overlay_path)

        summary: dict[str, Any] = {
            "prompt_index": prompt_index,
            "scores": scores.tolist(),
            "best_index": best_index,
            "area_pixels": int(best_mask.sum()),
            "coverage": float(best_mask.sum() / best_mask.size),
            "mask_bbox_xyxy": bbox,
            "overlay_path": str(overlay_path),
        }

        if prompt_index < len(prompt_points):
            points = prompt_points[prompt_index]
            labels = prompt_labels[prompt_index]
            summary["points"] = points
            summary["labels"] = labels
            summary["positive_points_inside"] = [
                bool(best_mask[y, x]) for (x, y), label in zip(points, labels, strict=False) if label == 1
            ]
            summary["negative_points_outside"] = [
                not bool(best_mask[y, x]) for (x, y), label in zip(points, labels, strict=False) if label == 0
            ]

        if prompt_index < len(prompt_boxes):
            summary["box"] = prompt_boxes[prompt_index]

        summaries.append(summary)

    return summaries


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(description="Run an end-to-end SAM2 image segmentation request.")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Python config file used when starting a local server (default: {DEFAULT_CONFIG})",
    )
    parser.add_argument(
        "--image",
        type=Path,
        default=DEFAULT_IMAGE,
        help=f"Image used for the request (default: {DEFAULT_IMAGE})",
    )
    parser.add_argument(
        "--model-name",
        default=DEFAULT_MODEL_NAME,
        help=f"Model name to call (default: {DEFAULT_MODEL_NAME})",
    )
    parser.add_argument(
        "--scenario",
        choices=["single-point", "docs-prompts", "box"],
        default="single-point",
        help="Preset request to run before any custom prompt overrides.",
    )
    parser.add_argument(
        "--server-url",
        default=None,
        help="Existing server URL. If omitted, the URL is built from --host/--port.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host used when starting a local server.")
    parser.add_argument("--port", type=int, default=7463, help="Port used when starting a local server.")
    parser.add_argument(
        "--no-start-server",
        action="store_true",
        help="Do not start a local server. Connect to --server-url or --host/--port instead.",
    )
    parser.add_argument(
        "--wait-timeout",
        type=int,
        default=240,
        help="Maximum time to wait for /ready when starting a local server.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for saved overlay images (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--point",
        action="append",
        type=parse_point,
        default=[],
        help="Custom point prompt in 'x,y' form. Repeat to add more points to one prompt.",
    )
    parser.add_argument(
        "--label",
        action="append",
        type=int,
        default=[],
        help="Label for each custom --point: 1 for foreground, 0 for background.",
    )
    parser.add_argument(
        "--box",
        type=parse_box,
        default=None,
        help="Custom box prompt in 'x1,y1,x2,y2' form.",
    )

    multimask_group = parser.add_mutually_exclusive_group()
    multimask_group.add_argument(
        "--multimask-output",
        dest="multimask_output",
        action="store_true",
        help="Request multiple candidate masks per prompt.",
    )
    multimask_group.add_argument(
        "--single-mask",
        dest="multimask_output",
        action="store_false",
        help="Request one mask per prompt.",
    )
    parser.set_defaults(multimask_output=None)

    return parser


async def main() -> None:
    """Run the end-to-end SAM2 image test."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.image.exists():
        raise FileNotFoundError(f"Image not found: {args.image}")

    if not args.no_start_server and not args.config.exists():
        raise FileNotFoundError(f"Config not found: {args.config}")

    payload = build_request_payload(args)
    image_bytes, image_data_url = image_to_data_url(args.image)
    base_url = args.server_url or f"http://{args.host}:{args.port}"

    server: InferenceServer | None = None
    ready_payload: dict[str, Any] | None = None

    try:
        if args.no_start_server:
            ready_payload = httpx.get(f"{base_url}/ready", timeout=5.0).json()
        else:
            server = InferenceServer()
            server.register_from_config(args.config)
            server.start(host=args.host, port=args.port, blocking=False)
            ready_payload = await wait_until_ready(base_url, args.wait_timeout)

        client = PixanoInferenceClient.connect(base_url)
        models = await client.list_models()
        if not any(model.name == args.model_name for model in models):
            available_models = ", ".join(model.name for model in models)
            raise ValueError(f"Model '{args.model_name}' not found. Available models: {available_models}")

        request = SegmentationRequest(
            model=args.model_name,
            image=image_data_url,
            **payload,
        )
        response = await client.segmentation(request)

        summary = {
            "base_url": base_url,
            "started_server": not args.no_start_server,
            "ready": ready_payload,
            "models": [model.model_dump() for model in models],
            "request": {
                "scenario": args.scenario,
                "model": args.model_name,
                **payload,
            },
            "response": {
                "status": response.status,
                "processing_time_s": response.processing_time,
                "results": summarize_masks(
                    response=response,
                    request_payload=payload,
                    image_bytes=image_bytes,
                    output_dir=args.output_dir,
                    scenario=args.scenario,
                ),
            },
        }
        print(json.dumps(summary, indent=2))
    finally:
        if server is not None:
            server.stop()


if __name__ == "__main__":
    asyncio.run(main())
