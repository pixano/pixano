/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { toDatasetSchema } from "$lib/api/adapters";
import type { DatasetResponse } from "$lib/api/restTypes";
import { loadWorkspaceRecord } from "$lib/api/workspace";
import {
  annotations,
  entities,
  resetWorkspaceStores,
  saveData,
} from "$lib/stores/workspaceStores.svelte";
import {
  BaseSchema,
  WorkspaceType,
  type Annotation,
  type Entity,
  type Tracklet,
} from "$lib/types/dataset";
import { OVERLAPIDS_SEPARATOR, relink } from "$lib/utils/entityRelink";
import { commitLoadedWorkspace } from "$lib/utils/workspaceRuntimeMutations";
import { buildWorkspaceManifest } from "$lib/workspace/manifest";

const DATASET_ID = "ds";
const RECORD_ID = "record-1";
const FRAME_INDEX = 0;
/** The number of frames of the record's video. */
const VIDEO_FRAME_COUNT = 5;

const frameId = (frameIndex: number): string => `frame-${frameIndex}`;
const FRAME_ID = frameId(FRAME_INDEX);
const NO_FEATURE_VALUES = { main: {}, objects: {} };

/** The resources the record loader lists, as the workspace manifest of a detection dataset. */
const RESOURCES = ["bboxes", "tracklets"];

type Row = Record<string, unknown>;

/** The rows the fake API holds, per resource path, as the gestures leave them once saved. */
let datasetRows: Record<string, Row[]> = {};

const fetchMock = vi.fn();

const page = (items: unknown[]) => ({ items, total: items.length, limit: 1000, offset: 0 });

const jsonResponse = (payload: unknown) =>
  new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });

/** Answers the loader's requests from `datasetRows`, the way the API lists one record's rows. */
function serveDataset(): void {
  fetchMock.mockImplementation((url: string) => {
    const resource = url.split("?")[0].slice(`/datasets/${DATASET_ID}/`.length);
    if (resource === `records/${RECORD_ID}`) {
      return Promise.resolve(jsonResponse({ id: RECORD_ID, created_at: "", updated_at: "" }));
    }
    if (resource === `records/${RECORD_ID}/images`) {
      const image = { id: FRAME_ID, record_id: RECORD_ID, logical_name: "image", src: "" };
      return Promise.resolve(jsonResponse(page([image])));
    }
    if (resource === `records/${RECORD_ID}/sframes`) {
      const frames = Array.from({ length: VIDEO_FRAME_COUNT }, (_, frameIndex) => ({
        id: frameId(frameIndex),
        record_id: RECORD_ID,
        logical_name: "video",
        src: "",
        frame_index: frameIndex,
      }));
      return Promise.resolve(jsonResponse(page(frames)));
    }
    return Promise.resolve(jsonResponse(page(datasetRows[resource] ?? [])));
  });
}

/** Opens the record in the workspace, through the loader and the stores the page uses. */
async function openRecord(workspaceType: WorkspaceType): Promise<void> {
  const { workspaceData } = await loadWorkspaceRecord(
    DATASET_ID,
    RECORD_ID,
    workspaceType,
    RESOURCES,
  );
  commitLoadedWorkspace(workspaceData, NO_FEATURE_VALUES);
}

/**
 * The writes the gesture queued for the next save, as `op resource/id`, sorted: the save sends
 * them in its own order.
 */
const queued = (): string[] =>
  saveData.value
    .map((mutation) => `${mutation.op} ${mutation.target.resource}/${mutation.target.id}`)
    .sort();

/** Applies the queued writes to the fake API's rows, as a save would. */
function saveQueued(): void {
  for (const mutation of saveData.value) {
    const rows = datasetRows[mutation.target.resource] ?? [];
    if (mutation.op === "delete") {
      datasetRows[mutation.target.resource] = rows.filter((row) => row.id !== mutation.target.id);
    } else if (mutation.op === "update") {
      datasetRows[mutation.target.resource] = rows.map((row) =>
        row.id === mutation.target.id ? { ...row, ...mutation.body } : row,
      );
    } else {
      datasetRows[mutation.target.resource] = [...rows, { ...mutation.body }];
    }
  }
}

const storedIds = (resource: string): string[] =>
  (datasetRows[resource] ?? []).map((row) => row.id as string);

const shownEntity = (id: string): Entity => {
  const entity = entities.value.find((candidate) => candidate.id === id);
  if (!entity) throw new Error(`The workspace does not show ${id}.`);
  return entity;
};

const shownEntityIds = (): string[] => entities.value.map((entity) => entity.id);

const shownAnnotation = (id: string): Annotation => {
  const annotation = annotations.value.find((candidate) => candidate.id === id);
  if (!annotation) throw new Error(`The workspace does not show ${id}.`);
  return annotation;
};

const shownTrack = (id: string): Tracklet => {
  const track = shownAnnotation(id);
  if (!track.is_type(BaseSchema.Tracklet)) throw new Error(`${id} is not a track.`);
  return track as Tracklet;
};

/** What the workspace shows of a track: its frames and the boxes that hang on it. */
const shownSpan = (id: string) => {
  const track = shownTrack(id);
  return {
    start: track.data.start_frame,
    end: track.data.end_frame,
    boxes: track.ui.childs.map((box) => box.id),
  };
};

const entityRow = (id: string, parentId = ""): Row => ({
  id,
  record_id: RECORD_ID,
  parent_id: parentId,
  created_at: "",
  updated_at: "",
});

const BOX = { coords: [0.1, 0.1, 0.2, 0.2], format: "xywh", is_normalized: true, confidence: 0.8 };

const boxRow = (
  id: string,
  entityId: string,
  source: Row,
  trackletId = "",
  frameIndex = FRAME_INDEX,
): Row => ({
  id,
  record_id: RECORD_ID,
  view_id: frameId(frameIndex),
  frame_id: frameId(frameIndex),
  entity_id: entityId,
  tracklet_id: trackletId,
  created_at: "",
  updated_at: "",
  ...BOX,
  ...source,
});

const trackRow = (
  id: string,
  entityId: string,
  source: Row,
  startFrame: number,
  endFrame: number,
): Row => ({
  id,
  record_id: RECORD_ID,
  view_id: frameId(startFrame),
  entity_id: entityId,
  start_timestep: startFrame,
  end_timestep: endFrame,
  created_at: "",
  updated_at: "",
  ...source,
});

const DRAWN_BY_A_PERSON = {
  source_type: "other",
  source_name: "Pixano",
  source_metadata: "{}",
};

/** A detection dataset's schema: one entity table and one box table. */
function detectionManifest(workspaceType: WorkspaceType) {
  const dataset: DatasetResponse = {
    id: DATASET_ID,
    path: "",
    previews_path: "",
    thumbnail: "",
    tables: { entities: "Entity", bboxes: "BBox", tracklets: "Tracklet" },
    feature_values: {},
    info: {
      id: DATASET_ID,
      name: "Detection",
      description: "",
      size: "",
      preview: "",
      creation_date: "",
      bookmarks: [],
      workspace: workspaceType,
      storage_mode: "embedded",
      num_records: 1,
      entity: { base: "Entity", name: "Entity", fields: {} },
      bbox: { base: "BBox", fields: {} },
      tracklet: { base: "Tracklet", fields: {} },
    },
  };
  return buildWorkspaceManifest(toDatasetSchema(dataset), workspaceType);
}

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  resetWorkspaceStores();
  datasetRows = {};
  serveDataset();
});

afterEach(() => {
  fetchMock.mockReset();
  vi.unstubAllGlobals();
  resetWorkspaceStores();
});

describe("a relink that merges a person's tracks", () => {
  // The relink saved only the boxes of the track it moved and the deletes. The boxes of a fused
  // track kept naming that deleted track, and the track they merged into kept its old span, so
  // the next load undid the merge.
  beforeEach(() => {
    // A person tracked a car over frames 0 and 1, then over frames 3 and 4, and a truck from
    // frame 1 to frame 3, with one box at frame 2, where the car has none.
    datasetRows = {
      entities: [entityRow("car"), entityRow("truck")],
      tracklets: [
        trackRow("track-car-early", "car", DRAWN_BY_A_PERSON, 0, 1),
        trackRow("track-car-late", "car", DRAWN_BY_A_PERSON, 3, 4),
        trackRow("track-truck", "truck", DRAWN_BY_A_PERSON, 1, 3),
      ],
      bboxes: [
        boxRow("box-car-0", "car", DRAWN_BY_A_PERSON, "track-car-early", 0),
        boxRow("box-car-1", "car", DRAWN_BY_A_PERSON, "track-car-early", 1),
        boxRow("box-car-3", "car", DRAWN_BY_A_PERSON, "track-car-late", 3),
        boxRow("box-car-4", "car", DRAWN_BY_A_PERSON, "track-car-late", 4),
        boxRow("box-truck-2", "truck", DRAWN_BY_A_PERSON, "track-truck", 2),
      ],
    };
  });

  it("saves the boxes it moves and the track it widens, which the next load shows", async () => {
    await openRecord(WorkspaceType.VIDEO);

    // The truck's track overlaps both tracks of the car, as the relink dialog finds them: it
    // merges into the first, and the second is fused into it.
    relink(
      shownAnnotation("track-truck"),
      shownEntity("truck"),
      "car",
      true,
      ["track-car-early", "track-car-late"].join(OVERLAPIDS_SEPARATOR),
      detectionManifest(WorkspaceType.VIDEO),
    );

    expect(queued()).toEqual([
      "delete entities/truck",
      "delete tracklets/track-car-late",
      "delete tracklets/track-truck",
      "update bboxes/box-car-3",
      "update bboxes/box-car-4",
      "update bboxes/box-truck-2",
      "update tracklets/track-car-early",
    ]);

    saveQueued();
    await openRecord(WorkspaceType.VIDEO);
    expect(storedIds("tracklets")).toEqual(["track-car-early"]);
    expect(shownEntityIds()).toEqual(["car"]);
    expect(shownSpan("track-car-early")).toEqual({
      start: 0,
      end: 4,
      boxes: ["box-car-0", "box-car-1", "box-truck-2", "box-car-3", "box-car-4"],
    });
  });
});
