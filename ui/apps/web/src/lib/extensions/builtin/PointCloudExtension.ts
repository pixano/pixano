/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { WidgetExtension } from "../WidgetExtension.js";
import { DEFAULT_TOOL_3D } from "$lib/annotations/scene/tool.js";
import type { PointCloudWidgetStorage } from "$lib/annotations/types.js";
import { toCameraCalibration } from "$lib/api/adapters.js";
import type { CalibratedImageResponse } from "$lib/api/restTypes.js";
import PointCloudWidget from "$lib/components/widgets/point-cloud/PointCloudWidget.svelte";
import type { ProjectionCameraSpec } from "$lib/pointcloud/cameraPixels.js";
import { DEFAULT_COLOR_MODE_ID } from "$lib/pointcloud/coloring/registry.js";
import { localStorageColorModePreferenceRepository } from "$lib/pointcloud/colorModePreferenceRepository.js";

/**
 * Bases this extension claims. `CalibratedPointCloud` extends `PointCloud`
 * on the backend; both ride through the same widget.
 */
const CLAIMED_BASES = new Set(["PointCloud", "CalibratedPointCloud"]);

/**
 * The record's cameras, reduced to what a projection needs.
 *
 * Uncalibrated images are dropped rather than passed along with a null
 * calibration: a camera you cannot project through is not a camera as far as
 * this widget is concerned, and dropping it here is what lets the projection
 * colour mode say "no calibrated camera" from the count alone.
 */
function toProjectionCameraSpecs(images: CalibratedImageResponse[]): ProjectionCameraSpec[] {
  return images.flatMap((image) => {
    const calibration = toCameraCalibration(image);
    if (!calibration || !image.src) return [];
    return [
      {
        id: image.id,
        name: image.logical_name ?? image.id,
        url: image.src,
        imageWidth: image.width ?? 0,
        imageHeight: image.height ?? 0,
        calibration,
      },
    ];
  });
}

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
    colorModeId: DEFAULT_COLOR_MODE_ID,
  }),
  addRecordSeed: async ({ datasetId, recordId, viewName, viewDef, gateway }) => {
    if (!viewDef.base || !CLAIMED_BASES.has(viewDef.base)) return null;

    // The cameras are fetched alongside the cloud, not on demand when the user
    // picks the projection colour mode: it is one record-scoped request either
    // way, and doing it here keeps the mode list's availability honest from the
    // first render instead of having "Camera colours" enabled itself later.
    const [pointCloud, images] = await Promise.all([
      gateway.loadPointCloudByLogicalName(datasetId, recordId, viewName),
      gateway.listRecordImages(datasetId, recordId).catch((err: unknown) => {
        // A camera listing that fails costs the projection mode, nothing else —
        // the cloud itself still renders.
        console.error("Failed to load the record's cameras:", err);
        return [] as CalibratedImageResponse[];
      }),
    ]);

    return {
      title: viewName,
      options: {},
      // Seeded, not left to `addStorage`: that factory runs per widget with no
      // knowledge of the dataset, so the user's choice would reset on every
      // record — exactly when stepping through a sequence needs it to hold.
      storage: {
        colorModeId:
          localStorageColorModePreferenceRepository.load(datasetId) ?? DEFAULT_COLOR_MODE_ID,
      },
      data: {
        pointCloudUrl: pointCloud?.src,
        datasetId,
        recordId,
        viewId: pointCloud?.id ?? "",
        /** World-to-sensor pose, for colour modes reasoning in the sensor frame. */
        worldToSensor: pointCloud?.extrinsic_matrix ?? null,
        cameras: toProjectionCameraSpecs(images),
      },
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
