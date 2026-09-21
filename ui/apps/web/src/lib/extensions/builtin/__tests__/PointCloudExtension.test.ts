/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { beforeEach, describe, expect, it, vi } from "vitest";

import { PointCloudExtension } from "../PointCloudExtension.js";
import type { CalibratedImageResponse, PointCloudResponse } from "$lib/api/restTypes.js";
import type { ProjectionCameraSpec } from "$lib/pointcloud/cameraPixels.js";
import { DEFAULT_COLOR_MODE_ID } from "$lib/pointcloud/coloring/registry.js";
import {
  COLOR_MODE_KEY_PREFIX,
  localStorageColorModePreferenceRepository,
} from "$lib/pointcloud/colorModePreferenceRepository.js";
import type { DatasetGateway } from "$lib/workspace/datasetGateway.js";

// The widget pulls in Threlte and Three; this test only exercises the seed.
vi.mock("$lib/components/widgets/point-cloud/PointCloudWidget.svelte", () => ({ default: {} }));

// ─── Helpers ─────────────────────────────────────────────────────────────────

const WORLD_TO_SENSOR = [1, 0, 0, -5, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];

const POINT_CLOUD: PointCloudResponse = {
  id: "LIDAR_TOP_0_0",
  record_id: "rec_0",
  logical_name: "LIDAR_TOP",
  src: "/cloud.bin",
  extrinsic_matrix: WORLD_TO_SENSOR,
  ego_to_world: null,
};

function makeImage(overrides: Partial<CalibratedImageResponse> = {}): CalibratedImageResponse {
  return {
    id: "CAM_FRONT_0_0",
    record_id: "rec_0",
    logical_name: "CAM_FRONT",
    src: "/cam.jpg",
    width: 1600,
    height: 900,
    f: [1266, 1266],
    c: [816, 491],
    distortion: [0],
    extrinsic_matrix: Array.from({ length: 16 }, (_, i) => i),
    ego_to_world: Array.from({ length: 16 }, (_, i) => i),
    ...overrides,
  };
}

interface GatewayOptions {
  pointCloud?: PointCloudResponse | null;
  images?: CalibratedImageResponse[];
  imagesFail?: boolean;
}

function makeGateway(options: GatewayOptions = {}): DatasetGateway {
  return {
    getDataset: () => Promise.resolve(null as never),
    listEntities: () => Promise.resolve([]),
    loadImageByLogicalName: () => Promise.resolve(null),
    listRecordImages: () =>
      options.imagesFail
        ? Promise.reject(new Error("cameras unavailable"))
        : Promise.resolve(options.images ?? []),
    listBBoxes: () => Promise.resolve([]),
    loadPointCloudByLogicalName: () =>
      Promise.resolve(options.pointCloud === undefined ? POINT_CLOUD : options.pointCloud),
    listBBox3Ds: () => Promise.resolve([]),
    createEntity: () => Promise.resolve({}),
    deleteEntity: () => Promise.resolve(),
    createAnnotation: () => Promise.resolve({}),
    updateAnnotation: () => Promise.resolve({}),
    deleteAnnotation: () => Promise.resolve(),
  };
}

function makeCtx(options: GatewayOptions = {}, base = "CalibratedPointCloud") {
  return {
    datasetId: "ds",
    recordId: "rec_0",
    viewName: "LIDAR_TOP",
    viewDef: { base },
    entitiesById: new Map(),
    gateway: makeGateway(options),
  };
}

async function seedData(options: GatewayOptions = {}): Promise<Record<string, unknown>> {
  const seed = await PointCloudExtension.config.addRecordSeed!(makeCtx(options));
  return (seed?.data ?? {}) as Record<string, unknown>;
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("PointCloudExtension storage", () => {
  it("opens on the default colour mode", () => {
    // The persisted choice has to start at a mode that runs on any cloud.
    expect(PointCloudExtension.config.addStorage!()).toMatchObject({
      colorModeId: DEFAULT_COLOR_MODE_ID,
    });
  });
});

describe("PointCloudExtension.addRecordSeed", () => {
  it("seeds the cloud url and the claimed view", async () => {
    const seed = await PointCloudExtension.config.addRecordSeed!(makeCtx());

    expect(seed).not.toBeNull();
    expect(seed!.data).toMatchObject({ pointCloudUrl: "/cloud.bin", viewId: "LIDAR_TOP_0_0" });
    expect(seed!.view).toEqual({
      id: "LIDAR_TOP_0_0",
      logicalName: "LIDAR_TOP",
      width: 0,
      height: 0,
    });
  });

  it("returns null for a view base it does not claim", async () => {
    const seed = await PointCloudExtension.config.addRecordSeed!(
      makeCtx({}, "CalibratedImage") as never,
    );
    expect(seed).toBeNull();
  });

  it("claims a plain PointCloud view too", async () => {
    const seed = await PointCloudExtension.config.addRecordSeed!(makeCtx({}, "PointCloud"));
    expect(seed).not.toBeNull();
  });

  // ─── Sensor pose ───────────────────────────────────────────────────────────

  it("seeds the sensor pose of a calibrated cloud", async () => {
    expect((await seedData()).worldToSensor).toEqual(WORLD_TO_SENSOR);
  });

  it("seeds a null pose for an uncalibrated cloud", async () => {
    // Null is meaningful: those clouds are already in the sensor frame, so the
    // distance mode treats it as the identity rather than as missing data.
    const pointCloud = { ...POINT_CLOUD, extrinsic_matrix: null };
    expect((await seedData({ pointCloud })).worldToSensor).toBeNull();
  });

  it("seeds a null pose when the cloud row is missing entirely", async () => {
    expect((await seedData({ pointCloud: null })).worldToSensor).toBeNull();
  });

  // ─── Cameras ───────────────────────────────────────────────────────────────

  it("seeds the record's calibrated cameras", async () => {
    const cameras = (await seedData({ images: [makeImage()] })).cameras as ProjectionCameraSpec[];

    expect(cameras).toHaveLength(1);
    expect(cameras[0]).toMatchObject({
      id: "CAM_FRONT_0_0",
      name: "CAM_FRONT",
      url: "/cam.jpg",
      imageWidth: 1600,
      imageHeight: 900,
    });
    expect(cameras[0].calibration.f).toEqual([1266, 1266]);
  });

  it("drops an uncalibrated camera", async () => {
    // A camera you cannot project through is not a camera here — dropping it is
    // what lets the projection mode judge availability from the count alone.
    const images = [makeImage({ extrinsic_matrix: null })];
    expect((await seedData({ images })).cameras).toEqual([]);
  });

  it("drops a camera with no media url", async () => {
    const images = [makeImage({ src: "" })];
    expect((await seedData({ images })).cameras).toEqual([]);
  });

  it("keeps the calibrated cameras and drops only the unusable ones", async () => {
    const images = [
      makeImage({ id: "a", logical_name: "CAM_A" }),
      makeImage({ id: "b", logical_name: "CAM_B", f: null }),
      makeImage({ id: "c", logical_name: "CAM_C" }),
    ];
    const cameras = (await seedData({ images })).cameras as ProjectionCameraSpec[];
    expect(cameras.map((camera) => camera.id)).toEqual(["a", "c"]);
  });

  it("still seeds the cloud when the camera listing fails", async () => {
    // The projection mode loses its cameras; the cloud must still render.
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    const data = await seedData({ imagesFail: true });

    expect(data.pointCloudUrl).toBe("/cloud.bin");
    expect(data.cameras).toEqual([]);
    consoleError.mockRestore();
  });
});

describe("PointCloudExtension colour-mode preference", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("seeds the default mode when the dataset has no remembered choice", async () => {
    const seed = await PointCloudExtension.config.addRecordSeed!(makeCtx());
    expect(seed!.storage).toMatchObject({ colorModeId: DEFAULT_COLOR_MODE_ID });
  });

  it("seeds the mode last chosen on this dataset", async () => {
    // The regression this guards: the choice used to live only in widget
    // storage, which `addStorage` rebuilds on every record load — so stepping
    // to the next record silently reset the mode to elevation.
    localStorageColorModePreferenceRepository.save("ds", "range");

    const seed = await PointCloudExtension.config.addRecordSeed!(makeCtx());

    expect(seed!.storage).toMatchObject({ colorModeId: "range" });
  });

  it("ignores a preference stored for another dataset", async () => {
    localStorageColorModePreferenceRepository.save("another-dataset", "range");
    const seed = await PointCloudExtension.config.addRecordSeed!(makeCtx());
    expect(seed!.storage).toMatchObject({ colorModeId: DEFAULT_COLOR_MODE_ID });
  });
});

describe("localStorageColorModePreferenceRepository", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("returns null for a dataset with no stored choice", () => {
    expect(localStorageColorModePreferenceRepository.load("ds")).toBeNull();
  });

  it("round-trips a mode id", () => {
    localStorageColorModePreferenceRepository.save("ds", "intensity");
    expect(localStorageColorModePreferenceRepository.load("ds")).toBe("intensity");
  });

  it("replaces a previous choice rather than accumulating", () => {
    localStorageColorModePreferenceRepository.save("ds", "intensity");
    localStorageColorModePreferenceRepository.save("ds", "range");
    expect(localStorageColorModePreferenceRepository.load("ds")).toBe("range");
  });

  it("keeps datasets independent", () => {
    localStorageColorModePreferenceRepository.save("a", "intensity");
    localStorageColorModePreferenceRepository.save("b", "range");
    expect(localStorageColorModePreferenceRepository.load("a")).toBe("intensity");
    expect(localStorageColorModePreferenceRepository.load("b")).toBe("range");
  });

  it("treats an empty stored value as no choice", () => {
    localStorage.setItem(`${COLOR_MODE_KEY_PREFIX}ds`, "");
    expect(localStorageColorModePreferenceRepository.load("ds")).toBeNull();
  });
});
