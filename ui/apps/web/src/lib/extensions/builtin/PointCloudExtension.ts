/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { DEFAULT_TOOL_3D } from "$lib/annotations/scene/tool.js";
import type { PointCloudWidgetStorage } from "$lib/annotations/types.js";
import PointCloudWidget from "$lib/components/widgets/point-cloud/PointCloudWidget.svelte";

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
    activeToolId: DEFAULT_TOOL_3D,
  }),
  addRecordSeed: async ({ datasetId, recordId, viewName, viewDef, gateway }) => {
    if (!viewDef.base || !CLAIMED_BASES.has(viewDef.base)) return null;

    const pointCloud = await gateway.loadPointCloudByLogicalName(datasetId, recordId, viewName);

    return {
      title: viewName,
      options: {},
      data: { pointCloudUrl: pointCloud?.src, datasetId, recordId, viewId: pointCloud?.id ?? "" },
      // 3D boxes are record-scoped; the bbox3d seed loader fetches them once
      // per record regardless of this view description.
      view: {
        id: pointCloud?.id ?? "",
        logicalName: viewName,
        width: 0,
        height: 0,
      },
    };
  },
});
