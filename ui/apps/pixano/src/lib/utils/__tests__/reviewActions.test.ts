/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { persistSaveItems } from "$lib/api/saveOrchestration";
import { loadWorkspaceRecord } from "$lib/api/workspace";
import { REVIEW_STATUS } from "$lib/constants/reviewConstants";
import {
  annotations,
  entities,
  highlightedEntity,
  preAnnotationIsActive,
  resetWorkspaceStores,
  reviewDecisionsLockedOn,
  saveData,
  selectedTool,
  workspaceSaveQueue,
} from "$lib/stores/workspaceStores.svelte";
import { fusionTool } from "$lib/tools";
import { Annotation, BaseSchema, WorkspaceType, type Entity } from "$lib/types/dataset";
import { ShapeType } from "$lib/types/shapeTypes";
import { applyNewShapeEditing } from "$lib/utils/entityAnnotationEditing";
import {
  acceptAnnotations,
  canTakeReviewDecision,
  createReviewReflection,
  rejectAnnotations,
  reviewTargetsOf,
} from "$lib/utils/reviewActions";
import { reviewStatusOf } from "$lib/utils/reviewStatus";
import { saveTo } from "$lib/utils/saveItemUtils";
import {
  commitLoadedWorkspace,
  commitNormalizedWorkspaceRuntime,
} from "$lib/utils/workspaceRuntimeMutations";

// A reviewer's decisions on a model's boxes, replayed through the real loader, stores and save,
// against a fake API that stores rows as the server's review rules do.

const DATASET_ID = "ds";
const RECORD_ID = "record-1";
const IMAGE_ID = "image-1";
const NO_FEATURE_VALUES = { main: {}, objects: {} };
const RESOURCES = ["bboxes"];

type Row = Record<string, unknown>;

/** The rows the fake API holds, per resource path. */
let datasetRows: Record<string, Row[]> = {};
/** The rows the fake API failed to read back, by id. */
let unreadable = new Set<string>();

const fetchMock = vi.fn();

const page = (items: unknown[]) => ({ items, total: items.length, limit: 1000, offset: 0 });

const jsonResponse = (payload: unknown, status = 200) =>
  new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });

const MODEL = {
  source_type: "model",
  source_name: "detection",
  source_metadata: '{"model": "yolo26n"}',
};
const PERSON = { source_type: "other", source_name: "Pixano", source_metadata: "{}" };

const entityRow = (id: string, category = "dog"): Row => ({
  id,
  record_id: RECORD_ID,
  parent_id: "",
  category,
  created_at: "",
  updated_at: "",
});

const boxRow = (id: string, entityId: string, source: Row, reviewStatus = ""): Row => ({
  id,
  record_id: RECORD_ID,
  view_id: IMAGE_ID,
  entity_id: entityId,
  coords: [0.1, 0.1, 0.2, 0.2],
  format: "xywh",
  is_normalized: true,
  confidence: 0.8,
  review_status: reviewStatus,
  created_at: "",
  updated_at: "",
  ...source,
});

const findRow = (resource: string, id: string): Row | undefined =>
  (datasetRows[resource] ?? []).find((row) => row.id === id);

/**
 * Stores an update as the server does (`_as_human_edit_of` in src/pixano/api/service.py, and
 * `acceptances_of_entity_edit` in src/pixano/api/review.py), as far as these tests go: a model's
 * box is stored accepted by an Accept or a change of its coordinates, and an entity whose category
 * changes accepts the model's boxes naming it that are still pending.
 */
function storeUpdate(resource: string, id: string, body: Row): Row {
  const stored = findRow(resource, id) ?? {};
  const updated: Row = { ...stored, ...body, id };
  if (resource === "bboxes" && stored.source_type === MODEL.source_type) {
    const accepts = body.review_status === REVIEW_STATUS.ACCEPTED;
    const moves = JSON.stringify(body.coords) !== JSON.stringify(stored.coords);
    updated.review_status = accepts || moves ? REVIEW_STATUS.ACCEPTED : stored.review_status;
  }
  if (resource === "entities" && body.category !== stored.category) {
    for (const box of datasetRows.bboxes ?? []) {
      if (
        box.entity_id === id &&
        box.source_type === MODEL.source_type &&
        box.review_status !== "accepted"
      ) {
        box.review_status = REVIEW_STATUS.ACCEPTED;
      }
    }
  }
  datasetRows[resource] = (datasetRows[resource] ?? []).map((row) =>
    row.id === id ? updated : row,
  );
  return updated;
}

function serveDataset(): void {
  fetchMock.mockImplementation((url: string, init?: RequestInit) => {
    const path = url.split("?")[0].slice(`/datasets/${DATASET_ID}/`.length);
    const [resource, id] = path.split("/");
    const method = init?.method ?? "GET";
    if (path === `records/${RECORD_ID}`) {
      return Promise.resolve(jsonResponse({ id: RECORD_ID, created_at: "", updated_at: "" }));
    }
    if (path === `records/${RECORD_ID}/images`) {
      const image = { id: IMAGE_ID, record_id: RECORD_ID, logical_name: "image", src: "" };
      return Promise.resolve(jsonResponse(page([image])));
    }
    if (method === "POST") {
      // A new row is stored as sent: a model's may carry a status (`check_new_row`).
      const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Row;
      datasetRows[resource] = [...(datasetRows[resource] ?? []), body];
      return Promise.resolve(jsonResponse(body, 201));
    }
    if (method === "PUT") {
      const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Row;
      return Promise.resolve(jsonResponse(storeUpdate(resource, id, body)));
    }
    if (method === "DELETE") {
      datasetRows[resource] = (datasetRows[resource] ?? []).filter((row) => row.id !== id);
      return Promise.resolve(new Response(null, { status: 204 }));
    }
    if (id !== undefined) {
      const row = findRow(resource, id);
      if (!row || unreadable.has(id)) return Promise.resolve(jsonResponse({}, 500));
      return Promise.resolve(jsonResponse(row));
    }
    return Promise.resolve(jsonResponse(page(datasetRows[resource] ?? [])));
  });
}

/** Opens the record, through the loader and the stores the page uses. */
async function openRecord(): Promise<void> {
  const { workspaceData } = await loadWorkspaceRecord(
    DATASET_ID,
    RECORD_ID,
    WorkspaceType.IMAGE,
    RESOURCES,
  );
  commitLoadedWorkspace(workspaceData, NO_FEATURE_VALUES);
}

/** Saves as the workspace page does, showing what the server stored of the review. */
async function save(): Promise<void> {
  const reflection = createReviewReflection(DATASET_ID);
  try {
    await persistSaveItems(workspaceSaveQueue, DATASET_ID, reflection.onPersisted);
  } finally {
    await reflection.finish();
  }
}

const shown = (id: string): Annotation => {
  const annotation = annotations.value.find((candidate) => candidate.id === id);
  if (!annotation) throw new Error(`The workspace does not show ${id}.`);
  return annotation;
};

const shownEntity = (id: string): Entity => {
  const entity = entities.value.find((candidate) => candidate.id === id);
  if (!entity) throw new Error(`The workspace does not show ${id}.`);
  return entity;
};

const queued = (): string[] =>
  saveData.value
    .map((mutation) => `${mutation.op} ${mutation.target.resource}/${mutation.target.id}`)
    .sort();

const queuedBody = (id: string): Row | undefined =>
  saveData.value.find((mutation) => mutation.target.id === id)?.body;

const readBacks = (): string[] =>
  fetchMock.mock.calls
    .filter(
      ([url, init]) => (init?.method ?? "GET") === "GET" && /\/bboxes\/[^/?]+$/.test(String(url)),
    )
    .map(([url]) => String(url));

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  vi.spyOn(console, "error").mockImplementation(() => {});
  resetWorkspaceStores();
  datasetRows = {};
  unreadable = new Set();
  serveDataset();
});

afterEach(() => {
  fetchMock.mockReset();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  resetWorkspaceStores();
});

describe("an Accept", () => {
  it("shows the box accepted at once, and saves it with the box's update", async () => {
    datasetRows = {
      entities: [entityRow("dog")],
      bboxes: [boxRow("box", "dog", MODEL, "pending")],
    };
    await openRecord();

    acceptAnnotations([shown("box")]);

    expect(reviewStatusOf(shown("box"))).toBe(REVIEW_STATUS.ACCEPTED);
    expect(queued()).toEqual(["update bboxes/box"]);
    // The status alone: the box is stored as the model wrote it.
    expect(queuedBody("box")).toEqual({ review_status: "accepted" });

    await save();

    expect(findRow("bboxes", "box")?.review_status).toBe("accepted");
    expect(shown("box").data.review_status).toBe("accepted");
    expect(shown("box").ui.unsavedAccept).toBe(false);
    expect(reviewStatusOf(shown("box"))).toBe(REVIEW_STATUS.ACCEPTED);
  });

  it("of all accepts each box still to review, and only those", async () => {
    datasetRows = {
      entities: [entityRow("dog"), entityRow("cat"), entityRow("bird"), entityRow("drawn")],
      bboxes: [
        boxRow("dog-box", "dog", MODEL, "pending"),
        boxRow("cat-box", "cat", MODEL, ""),
        boxRow("bird-box", "bird", MODEL, "accepted"),
        boxRow("drawn-box", "drawn", PERSON),
      ],
    };
    await openRecord();

    acceptAnnotations(annotations.value);

    expect(queued()).toEqual(["update bboxes/cat-box", "update bboxes/dog-box"]);
  });

  it("left unsaved is dropped with the record", async () => {
    datasetRows = {
      entities: [entityRow("dog")],
      bboxes: [boxRow("box", "dog", MODEL, "pending")],
    };
    await openRecord();
    acceptAnnotations([shown("box")]);

    // Leaving without saving: the next opening reads the record as the dataset holds it.
    await openRecord();

    expect(reviewStatusOf(shown("box"))).toBe(REVIEW_STATUS.PENDING);
    expect(queued()).toEqual([]);
  });

  it("rides on an edit of the box staged before it, the box sent whole", async () => {
    datasetRows = {
      entities: [entityRow("dog")],
      bboxes: [boxRow("box", "dog", MODEL, "pending")],
    };
    await openRecord();
    const box = shown("box");
    box.data.coords = [0.3, 0.3, 0.2, 0.2];
    saveTo("update", box);

    acceptAnnotations([shown("box")]);

    expect(queued()).toEqual(["update bboxes/box"]);
    expect(queuedBody("box")).toMatchObject({
      review_status: "accepted",
      coords: [0.3, 0.3, 0.2, 0.2],
    });
  });

  it("rides on an edit of the box being saved, the box sent whole", async () => {
    // Were the save of the edit refused, the queue would put it back under the Accept staged
    // since: the Accept must hold the edit too.
    datasetRows = {
      entities: [entityRow("dog")],
      bboxes: [boxRow("box", "dog", MODEL, "pending")],
    };
    await openRecord();
    const box = shown("box");
    box.data.coords = [0.3, 0.3, 0.2, 0.2];
    saveTo("update", box);
    let answerTheEdit!: () => void;
    const serve = fetchMock.getMockImplementation();
    fetchMock.mockImplementationOnce(
      (url: string, init?: RequestInit) =>
        new Promise<Response>((resolve) => {
          answerTheEdit = () => resolve(serve?.(url, init));
        }),
    );
    const saving = save();

    acceptAnnotations([shown("box")]);
    const accept = saveData.value.at(-1);
    answerTheEdit();
    await saving;

    expect(accept?.body).toMatchObject({
      review_status: "accepted",
      coords: [0.3, 0.3, 0.2, 0.2],
    });
  });

  it("rides with an edit of the box made after it", async () => {
    datasetRows = {
      entities: [entityRow("dog")],
      bboxes: [boxRow("box", "dog", MODEL, "pending")],
    };
    await openRecord();
    acceptAnnotations([shown("box")]);

    const box = shown("box");
    box.data.coords = [0.3, 0.3, 0.2, 0.2];
    saveTo("update", box);

    expect(queued()).toEqual(["update bboxes/box"]);
    expect(queuedBody("box")).toMatchObject({
      review_status: "accepted",
      coords: [0.3, 0.3, 0.2, 0.2],
    });
  });
});

describe("a Reject", () => {
  it("deletes the box, with its object when the box was all it had", async () => {
    datasetRows = {
      entities: [entityRow("dog")],
      bboxes: [boxRow("box", "dog", MODEL, "pending")],
    };
    await openRecord();

    rejectAnnotations([shown("box")]);

    expect(annotations.value).toEqual([]);
    expect(entities.value).toEqual([]);
    expect(queued()).toEqual(["delete bboxes/box", "delete entities/dog"]);
  });

  it("of all an object's boxes deletes each, and the object with the last", async () => {
    datasetRows = {
      entities: [entityRow("dog")],
      bboxes: [boxRow("first", "dog", MODEL, "pending"), boxRow("second", "dog", MODEL, "")],
    };
    await openRecord();

    rejectAnnotations(shownEntity("dog").ui.childs ?? []);

    expect(annotations.value).toEqual([]);
    expect(entities.value).toEqual([]);
    expect(queued()).toEqual([
      "delete bboxes/first",
      "delete bboxes/second",
      "delete entities/dog",
    ]);
  });

  it("keeps the object's other annotations", async () => {
    datasetRows = {
      entities: [entityRow("dog")],
      bboxes: [boxRow("proposed", "dog", MODEL, "pending"), boxRow("drawn", "dog", PERSON)],
    };
    await openRecord();

    rejectAnnotations([shown("proposed")]);

    expect(annotations.value.map((annotation) => annotation.id)).toEqual(["drawn"]);
    expect(shownEntity("dog").ui.childs?.map((annotation) => annotation.id)).toEqual(["drawn"]);
    expect(queued()).toEqual(["delete bboxes/proposed"]);
  });

  it("of an object's last annotation drops the focus on it, which would fade every annotation", async () => {
    datasetRows = {
      entities: [entityRow("dog"), entityRow("cat")],
      bboxes: [boxRow("box", "dog", MODEL, "pending"), boxRow("drawn", "cat", PERSON)],
    };
    await openRecord();
    highlightedEntity.value = "dog";

    rejectAnnotations([shown("box")]);

    expect(highlightedEntity.value).toBeNull();
  });

  it("keeps the focus on an object it leaves standing", async () => {
    datasetRows = {
      entities: [entityRow("dog")],
      bboxes: [boxRow("proposed", "dog", MODEL, "pending"), boxRow("drawn", "dog", PERSON)],
    };
    await openRecord();
    highlightedEntity.value = "dog";

    rejectAnnotations([shown("proposed")]);

    expect(highlightedEntity.value).toBe("dog");
  });
});

describe("a decision on a box not to review", () => {
  it.each([
    ["a person's box", PERSON, ""],
    ["a box already accepted", MODEL, "accepted"],
  ])("is not taken on %s", async (_, source, reviewStatus) => {
    datasetRows = {
      entities: [entityRow("dog")],
      bboxes: [boxRow("box", "dog", source, reviewStatus)],
    };
    await openRecord();

    acceptAnnotations([shown("box")]);
    rejectAnnotations([shown("box")]);

    expect(queued()).toEqual([]);
    expect(annotations.value.map((annotation) => annotation.id)).toEqual(["box"]);
  });
});

describe("after a save", () => {
  it("shows a model's box accepted by the saved edit of it", async () => {
    datasetRows = {
      entities: [entityRow("dog")],
      bboxes: [boxRow("box", "dog", MODEL, "pending")],
    };
    await openRecord();
    const box = shown("box");
    box.data.coords = [0.3, 0.3, 0.2, 0.2];
    saveTo("update", box);
    expect(reviewStatusOf(shown("box"))).toBe(REVIEW_STATUS.PENDING);

    await save();

    expect(reviewStatusOf(shown("box"))).toBe(REVIEW_STATUS.ACCEPTED);
  });

  it("shows the model's boxes an edit of their object accepted, read back", async () => {
    datasetRows = {
      entities: [entityRow("dog"), entityRow("cat")],
      bboxes: [
        boxRow("dog-box", "dog", MODEL, "pending"),
        boxRow("dog-box-accepted", "dog", MODEL, "accepted"),
        boxRow("cat-box", "cat", MODEL, "pending"),
      ],
    };
    await openRecord();
    const dog = shownEntity("dog");
    dog.data = { ...dog.data, category: "wolf" };
    saveTo("update", dog);

    await save();

    expect(reviewStatusOf(shown("dog-box"))).toBe(REVIEW_STATUS.ACCEPTED);
    expect(reviewStatusOf(shown("cat-box"))).toBe(REVIEW_STATUS.PENDING);
    expect(readBacks()).toEqual([`/datasets/${DATASET_ID}/bboxes/dog-box`]);
  });

  it("leaves a box shown pending when an edit of its object accepted nothing", async () => {
    datasetRows = {
      entities: [entityRow("dog")],
      bboxes: [boxRow("box", "dog", MODEL, "pending")],
    };
    await openRecord();
    saveTo("update", shownEntity("dog"));

    await save();

    expect(reviewStatusOf(shown("box"))).toBe(REVIEW_STATUS.PENDING);
  });

  it("leaves a box it cannot read back as it was shown, and the save done", async () => {
    datasetRows = {
      entities: [entityRow("dog")],
      bboxes: [boxRow("box", "dog", MODEL, "pending")],
    };
    unreadable.add("box");
    await openRecord();
    const dog = shownEntity("dog");
    dog.data = { ...dog.data, category: "wolf" };
    saveTo("update", dog);

    await save();

    expect(reviewStatusOf(shown("box"))).toBe(REVIEW_STATUS.PENDING);
    expect(queued()).toEqual([]);
  });

  it("never shows a box taken back from accepted", async () => {
    datasetRows = {
      entities: [entityRow("dog")],
      bboxes: [boxRow("box", "dog", MODEL, "pending")],
    };
    await openRecord();
    acceptAnnotations([shown("box")]);
    const update = saveData.value[0];

    // A write of the box landing with its stored status still pending, as one sent before the
    // Accept: the Accept is still to save.
    createReviewReflection(DATASET_ID).onPersisted(update, { id: "box", review_status: "pending" });

    expect(reviewStatusOf(shown("box"))).toBe(REVIEW_STATUS.ACCEPTED);
    expect(shown("box").ui.unsavedAccept).toBe(true);
  });
});

describe("an edit of a model's box, through the canvas", () => {
  /** The edit the canvas hands the workspace once a box is moved, in the box's coordinates. */
  const moveBox = (id: string, coords: number[]) =>
    applyNewShapeEditing({
      status: "editing",
      shapeId: id,
      viewRef: { id: IMAGE_ID, name: "image" },
      type: ShapeType.bbox,
      coords,
    });

  it("leaves the box in review, still the model's, until it is saved", async () => {
    // The server keeps a model's source through a person's edit, and the review reads it.
    datasetRows = {
      entities: [entityRow("dog")],
      bboxes: [boxRow("box", "dog", MODEL, "pending")],
    };
    await openRecord();

    moveBox("box", [0.3, 0.3, 0.2, 0.2]);

    expect(reviewStatusOf(shown("box"))).toBe(REVIEW_STATUS.PENDING);
    expect(queuedBody("box")).toMatchObject({ source_type: "model", coords: [0.3, 0.3, 0.2, 0.2] });

    await save();

    expect(reviewStatusOf(shown("box"))).toBe(REVIEW_STATUS.ACCEPTED);
  });

  it("keeps an Accept taken before it", async () => {
    datasetRows = {
      entities: [entityRow("dog")],
      bboxes: [boxRow("box", "dog", MODEL, "pending")],
    };
    await openRecord();
    acceptAnnotations([shown("box")]);

    moveBox("box", [0.3, 0.3, 0.2, 0.2]);

    expect(queuedBody("box")).toMatchObject({
      review_status: "accepted",
      coords: [0.3, 0.3, 0.2, 0.2],
    });
  });
});

describe("a decision", () => {
  beforeEach(async () => {
    datasetRows = {
      entities: [entityRow("dog")],
      bboxes: [boxRow("box", "dog", MODEL, "pending")],
    };
    await openRecord();
  });

  it.each([
    ["under the Fusion tool, which merges objects", () => (selectedTool.value = fusionTool)],
    [
      "while the old pre-annotation mode hides the objects",
      () => (preAnnotationIsActive.value = true),
    ],
    ["on the record Save & next is leaving", () => (reviewDecisionsLockedOn.value = RECORD_ID)],
  ])("is not taken %s", (_, setUp) => {
    setUp();

    expect(canTakeReviewDecision()).toBe(false);
    acceptAnnotations([shown("box")]);
    rejectAnnotations([shown("box")]);
    expect(queued()).toEqual([]);
  });

  it("is taken on another record than the one Save & next is leaving", () => {
    // The reviewer moved on while the queue answered.
    reviewDecisionsLockedOn.value = "the-record-left";

    expect(canTakeReviewDecision()).toBe(true);
  });

  it("on an object covers what it shows still to review: a hidden one stays", async () => {
    datasetRows = {
      entities: [entityRow("dog")],
      bboxes: [boxRow("box", "dog", MODEL, "pending"), boxRow("hidden", "dog", MODEL, "pending")],
    };
    await openRecord();
    const hidden = shown("hidden");
    hidden.ui.displayControl = { ...hidden.ui.displayControl, hidden: true };

    expect(reviewTargetsOf(shownEntity("dog")).map((annotation) => annotation.id)).toEqual(["box"]);
  });
});

describe("an Accept of a model's row made in this session", () => {
  it("rides on its create, and shows accepted once saved", async () => {
    // The legacy smart segmentation stores a model's mask with no status: it reads pending.
    datasetRows = { entities: [entityRow("dog")], bboxes: [] };
    await openRecord();
    const made = Annotation.deepCreateInstanceArray({
      bboxes: [
        {
          id: "made",
          created_at: "",
          updated_at: "",
          table_info: { name: "bboxes", group: "annotations", base_schema: BaseSchema.BBox },
          data: {
            ...boxRow("made", "dog", MODEL),
            view_name: "image",
            item_id: RECORD_ID,
          },
        },
      ],
    }).bboxes[0];
    made.ui.datasetItemType = WorkspaceType.IMAGE;
    commitNormalizedWorkspaceRuntime([...annotations.value, made], entities.value);
    saveTo("add", made);

    acceptAnnotations([shown("made")]);

    expect(queued()).toEqual(["create bboxes/made"]);
    expect(queuedBody("made")).toMatchObject({ review_status: "accepted" });

    await save();

    expect(shown("made").ui.unsavedAccept).toBe(false);
    expect(reviewStatusOf(shown("made"))).toBe(REVIEW_STATUS.ACCEPTED);
  });
});
