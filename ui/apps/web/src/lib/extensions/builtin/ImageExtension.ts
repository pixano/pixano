/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { DEFAULT_TOOL_2D } from "$lib/annotations/scene/tool.js";
import type {
  CameraCalibration,
  ImageWidgetOptions,
  ImageWidgetStorage,
} from "$lib/annotations/types.js";
import type { CalibratedImageResponse } from "$lib/api/restTypes.js";
import ImageWidget from "$lib/components/widgets/image/ImageWidget.svelte";

import { WidgetExtension } from "../WidgetExtension.js";

/**
 * Bases this extension claims. `CalibratedImage` extends `Image` on the
 * backend and now surfaces calibration data via `options.calibration`.
 */
const CLAIMED_BASES = new Set(["Image", "CalibratedImage"]);

function _extractCalibration(image: CalibratedImageResponse | null): CameraCalibration | null {
  if (!image?.extrinsic_matrix || !image.ego_to_world || !image.f || !image.c || !image.distortion) {
    return null;
  }
  return {
    f: image.f,
    c: image.c,
    distortion: image.distortion,
    extrinsicMatrix: image.extrinsic_matrix,
    egoToWorld: image.ego_to_world,
  };
}

export const ImageExtension = WidgetExtension.create<ImageWidgetOptions, ImageWidgetStorage>({
  name: "image",
  label: "2D Canvas",
  icon: "image",
  priority: 100,
  defaultLayout: { x: 0, y: 0, w: 6, h: 5, minW: 3, minH: 3 },
  component: ImageWidget,
  addOptions: () => ({
    datasetId: "",
    recordId: "",
    viewId: "",
    viewName: "",
    imageWidth: 0,
    imageHeight: 0,
    calibration: null,
  }),
  addStorage: () => ({
    activeToolId: DEFAULT_TOOL_2D,
  }),
  addRecordSeed: async ({ datasetId, recordId, viewName, viewDef, gateway }) => {
    if (!viewDef.base || !CLAIMED_BASES.has(viewDef.base)) return null;

    const image = await gateway.loadImageByLogicalName(datasetId, recordId, viewName);

    return {
      title: viewName,
      options: {
        datasetId,
        recordId,
        viewId: image?.id ?? "",
        viewName,
        imageWidth: image?.width ?? 0,
        imageHeight: image?.height ?? 0,
        calibration: _extractCalibration(image),
      },
      data: { imageUrl: image?.src },
      // The per-kind SEED_LOADERS fetch this record's annotations once and
      // resolve their rows against this view description.
      view: {
        id: image?.id ?? "",
        logicalName: viewName,
        width: image?.width ?? 0,
        height: image?.height ?? 0,
      },
    };
  },
});
