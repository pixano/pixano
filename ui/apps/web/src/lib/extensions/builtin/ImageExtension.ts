/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type {
  CameraCalibration,
  CoordsNorm,
  ImageWidgetOptions,
  ImageWidgetStorage,
  LocalBBox,
} from "$lib/annotations/types.js";
import type { BBoxRow } from "$lib/api/annotations.js";
import type { CalibratedImageResponse } from "$lib/api/restTypes.js";
import ImageWidget from "$lib/components/widgets/ImageWidget.svelte";

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
    mode: "select",
    selectedId: null,
    bboxes: [],
  }),
  findLocalDraft: (storage, localId) => {
    return (storage as ImageWidgetStorage).bboxes?.find((b) => b.id === localId);
  },
  addRecordSeed: async ({ datasetId, recordId, viewName, viewDef, entitiesById, gateway }) => {
    if (!viewDef.base || !CLAIMED_BASES.has(viewDef.base)) return null;

    const image = await gateway.loadImageByLogicalName(datasetId, recordId, viewName);

    // Pre-fetch bboxes for this view. We load all record bboxes and filter
    // client-side, matching both the image row id (new annotations) and the
    // view logical name (legacy annotations where view_id was the camera name
    // rather than the image row id) so existing data is always visible.
    const allBBoxes = image
      ? await gateway
          .listBBoxes(datasetId, { recordId })
          .catch(() => [] as BBoxRow[])
      : [];

    const existingBBoxes = allBBoxes.filter(
      (b) => b.view_id === image?.id || b.view_id === viewName,
    );

    const iw = image?.width ?? 1;
    const ih = image?.height ?? 1;

    const seedBBoxes = existingBBoxes
      .filter((b) => Array.isArray(b.coords) && b.coords.length === 4)
      .map<LocalBBox>((b) => {
        // Convert pixel-space coords to normalized [0,1] if needed.
        // Backend stores xywh or xyxy; we normalise to xywh here.
        let [a, c_b, w, h] = b.coords;
        if (b.format === "xyxy") {
          w = w - a;
          h = h - c_b;
        }
        const coordsNorm: CoordsNorm = b.is_normalized
          ? [a, c_b, w, h]
          : [a / iw, c_b / ih, w / iw, h / ih];
        return {
          id: b.id,
          entityId: b.entity_id,
          coordsNorm,
          persisted: true,
          entity: entitiesById.get(b.entity_id),
        };
      });

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
      storage: { bboxes: seedBBoxes },
    };
  },
});
