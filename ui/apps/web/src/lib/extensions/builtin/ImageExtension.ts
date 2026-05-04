/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type {
  CoordsNorm,
  ImageWidgetOptions,
  ImageWidgetStorage,
  LocalBBox,
} from "$lib/annotations/types.js";
import type { BBoxRow } from "$lib/api/annotations.js";
import ImageWidget from "$lib/components/widgets/ImageWidget.svelte";

import { WidgetExtension } from "../WidgetExtension.js";

/**
 * Bases this extension claims. `CalibratedImage` extends `Image` on the
 * backend (extra calibration fields the UI ignores for now), so it goes
 * through the same widget and endpoint.
 */
const CLAIMED_BASES = new Set(["Image", "CalibratedImage"]);

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
  }),
  addStorage: () => ({
    mode: "select",
    selectedId: null,
    bboxes: [],
  }),
  addRecordSeed: async ({ datasetId, recordId, viewName, viewDef, entitiesById, gateway }) => {
    if (!viewDef.base || !CLAIMED_BASES.has(viewDef.base)) return null;

    const image = await gateway.loadImageByLogicalName(datasetId, recordId, viewName);

    // Pre-fetch any bboxes already stored for this (record, view) pair so
    // we can hand them to the widget at mount time. If the fetch fails we
    // log and fall back to an empty list — the user can still draw new
    // boxes.
    const existingBBoxes = image?.id
      ? await gateway
          .listBBoxes(datasetId, { recordId, viewId: image.id })
          .catch((err) => {
            console.error("listBBoxes failed", err);
            return [] as BBoxRow[];
          })
      : [];

    const seedBBoxes = existingBBoxes
      .filter((b) => Array.isArray(b.coords) && b.coords.length === 4 && b.is_normalized)
      .map<LocalBBox>((b) => ({
        id: b.id,
        entityId: b.entity_id,
        coordsNorm: [...b.coords] as CoordsNorm,
        persisted: true,
        // Attach the parent entity (when one exists) so the widget can
        // render a label without an extra fetch.
        entity: entitiesById.get(b.entity_id),
      }));

    return {
      title: viewName,
      options: {
        datasetId,
        recordId,
        viewId: image?.id ?? "",
        viewName,
        imageWidth: image?.width ?? 0,
        imageHeight: image?.height ?? 0,
      },
      data: { imageUrl: image?.src },
      storage: { bboxes: seedBBoxes },
    };
  },
});
