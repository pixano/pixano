/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { BBox3DRow, LocalBBox3D } from "$lib/api/annotations.js";
import type { PointCloudWidgetStorage } from "$lib/annotations/types.js";
import PointCloudWidget from "$lib/components/widgets/PointCloudWidget.svelte";

import { WidgetExtension } from "../WidgetExtension.js";

/**
 * Bases this extension claims. `CalibratedPointCloud` extends `PointCloud`
 * on the backend; both ride through the same widget.
 */
const CLAIMED_BASES = new Set(["PointCloud", "CalibratedPointCloud"]);

export const PointCloudExtension = WidgetExtension.create({
  name: "point-cloud",
  label: "3D Viewer",
  icon: "box",
  priority: 90,
  defaultLayout: { x: 6, y: 0, w: 6, h: 5, minW: 3, minH: 3 },
  component: PointCloudWidget,
  addOptions: () => ({
    pointSize: 0.08,
    backgroundColor: "#1e293b",
    logicalName: "",
  }),
  addStorage: (): PointCloudWidgetStorage => ({
    mode: "navigate",
    drafts: [],
  }),
  findLocalDraft: (storage, localId) => {
    return (storage as PointCloudWidgetStorage).drafts?.find((b) => b.id === localId);
  },
  addRecordSeed: async ({ datasetId, recordId, viewName, viewDef, entitiesById, gateway }) => {
    if (!viewDef.base || !CLAIMED_BASES.has(viewDef.base)) return null;

    // 3D boxes are typically expressed in the record's ego/world frame and
    // stored without a `view_id` (since they apply to the whole scene, not
    // a single sensor). We therefore scope the listing to the record only.
    // If a dataset later attaches boxes to a specific point-cloud view,
    // the backend just returns the record-scoped superset.
    //
    // Fetched in parallel with the point cloud blob — they don't depend on
    // each other, and this is the most common per-record latency offender.
    const [pointCloud, bboxRows] = await Promise.all([
      gateway.loadPointCloudByLogicalName(datasetId, recordId, viewName),
      gateway.listBBox3Ds(datasetId, { recordId }).catch((err) => {
        console.error("listBBox3Ds failed", err);
        return [] as BBox3DRow[];
      }),
    ]);

    // Attach the parent entity (when one exists) so the scene can render a
    // label via `pickEntityLabel` without an extra fetch.
    const bboxes3d: LocalBBox3D[] = bboxRows.map((b) => ({
      ...b,
      entity: b.entity_id ? entitiesById.get(b.entity_id) : undefined,
    }));

    return {
      title: viewName,
      options: {},
      data: { pointCloudUrl: pointCloud?.src, bboxes3d, datasetId, recordId, viewId: pointCloud?.id ?? "" },
    };
  },
});
