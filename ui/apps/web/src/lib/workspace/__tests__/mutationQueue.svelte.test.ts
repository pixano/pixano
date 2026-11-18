/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { afterEach, describe, expect, it, vi } from "vitest";

import { httpDatasetGateway, type MutationGateway } from "../datasetGateway.js";
import { MutationQueue, type LocalAnnotationLocator } from "../mutationQueue.svelte.js";
import { WorkspaceSession } from "../workspaceSession.svelte.js";
import type { ResourceMutation } from "$lib/annotations/types.js";
import { ApiError } from "$lib/api/apiClient.js";
import { ENTITY_RESOURCE } from "$lib/api/resourceNames.js";

// ─── Test scaffolding ───────────────────────────────────────────────────────

interface GatewayCall {
  method: keyof MutationGateway;
  args: unknown[];
}

function makeGateway(opts: { failOn?: keyof MutationGateway; error?: Error } = {}) {
  const calls: GatewayCall[] = [];
  // Synchronous accounting + opt-in throw. We then return resolved
  // promises so the helpers themselves can stay non-async (eslint:
  // require-await would complain about an async body that never awaits).
  const record = (m: keyof MutationGateway, args: unknown[]) => {
    calls.push({ method: m, args });
    if (m === opts.failOn) throw opts.error ?? new Error("boom");
  };
  const gateway: MutationGateway = {
    createEntity: (...args) => {
      record("createEntity", args);
      return Promise.resolve({});
    },
    deleteEntity: (...args) => {
      record("deleteEntity", args);
      return Promise.resolve();
    },
    createAnnotation: (...args) => {
      record("createAnnotation", args);
      return Promise.resolve({});
    },
    updateAnnotation: (...args) => {
      record("updateAnnotation", args);
      return Promise.resolve({});
    },
    deleteAnnotation: (...args) => {
      record("deleteAnnotation", args);
      return Promise.resolve();
    },
  };
  return { gateway, calls };
}

function makeSession(datasetId: string | null = "ds-1"): WorkspaceSession {
  const session = new WorkspaceSession();
  session.datasetId = datasetId;
  return session;
}

const noopLocator: LocalAnnotationLocator = {
  findLocalAnnotation: () => undefined,
};

// ─── Tests ──────────────────────────────────────────────────────────────────

describe("MutationQueue.upsertUpdate", () => {
  function update(
    id: string,
    body: Record<string, unknown>,
  ): Extract<ResourceMutation, { op: "update" }> {
    return { op: "update", resource: "bboxes", id, body };
  }

  it("queues an update when none is pending for that resource+id", () => {
    const { gateway } = makeGateway();
    const queue = new MutationQueue(gateway, makeSession(), noopLocator);

    queue.upsertUpdate(update("b1", { coords: [0, 0, 1, 1] }));

    expect(queue.count).toBe(1);
    expect(queue.pending[0]).toMatchObject({
      op: "update",
      id: "b1",
      body: { coords: [0, 0, 1, 1] },
    });
  });

  it("replaces the body of the pending update instead of adding a second one", () => {
    const { gateway } = makeGateway();
    const queue = new MutationQueue(gateway, makeSession(), noopLocator);

    queue.upsertUpdate(update("b1", { coords: [0, 0, 1, 1] }));
    queue.upsertUpdate(update("b1", { coords: [9, 9, 2, 2] }));

    expect(queue.count).toBe(1);
    expect(queue.pending[0]).toMatchObject({ body: { coords: [9, 9, 2, 2] } });
  });

  it("keeps updates for different ids separate", () => {
    const { gateway } = makeGateway();
    const queue = new MutationQueue(gateway, makeSession(), noopLocator);

    queue.upsertUpdate(update("b1", { v: 1 }));
    queue.upsertUpdate(update("b2", { v: 2 }));

    expect(queue.count).toBe(2);
  });
});

describe("MutationQueue.patchPendingCreate", () => {
  it("merges the patch into a pending create's body", () => {
    const { gateway } = makeGateway();
    const queue = new MutationQueue(gateway, makeSession(), noopLocator);
    queue.queue({
      op: "create",
      resource: "bboxes",
      body: { id: "b1", coords: [0, 0, 1, 1] },
      localAnnotationId: "b1",
    } as ResourceMutation);

    queue.patchPendingCreate("b1", "bboxes", { coords: [5, 5, 2, 2] });

    expect(queue.count).toBe(1);
    expect(queue.pending[0]).toMatchObject({
      op: "create",
      body: { id: "b1", coords: [5, 5, 2, 2] },
    });
  });

  it("is a no-op when no matching pending create exists", () => {
    const { gateway } = makeGateway();
    const queue = new MutationQueue(gateway, makeSession(), noopLocator);

    queue.patchPendingCreate("ghost", "bboxes", { coords: [1, 2, 3, 4] });

    expect(queue.count).toBe(0);
  });

  it("does not patch a create of a different resource or id", () => {
    const { gateway } = makeGateway();
    const queue = new MutationQueue(gateway, makeSession(), noopLocator);
    queue.queue({
      op: "create",
      resource: "bbox3ds",
      body: { id: "b1", coords: [0, 0, 0, 1, 1, 1] },
      localAnnotationId: "b1",
    } as ResourceMutation);

    queue.patchPendingCreate("b1", "bboxes", { coords: [9, 9, 9, 9] });

    expect(queue.pending[0]).toMatchObject({ body: { coords: [0, 0, 0, 1, 1, 1] } });
  });
});

describe("MutationQueue.flush", () => {
  it("does nothing when there's no dataset selected", async () => {
    const { gateway, calls } = makeGateway();
    const queue = new MutationQueue(gateway, makeSession(null), noopLocator);

    queue.queue({ op: "create", resource: "bboxes", body: {} } as ResourceMutation);
    await queue.flush();

    expect(calls).toEqual([]);
    expect(queue.saveError).toBe("No dataset selected.");
    expect(queue.saving).toBe(false);
    // pending isn't reset on a no-dataset early return — the user can fix
    // the selection and try again.
    expect(queue.count).toBe(1);
  });

  it("orders entity creates before bbox creates and runs deletes last", async () => {
    const { gateway, calls } = makeGateway();
    const queue = new MutationQueue(gateway, makeSession(), noopLocator);

    queue.queue({
      op: "delete",
      resource: "bboxes",
      id: "old-bb",
    } as ResourceMutation);
    queue.queue({
      op: "create",
      resource: "bboxes",
      body: { id: "new-bb" },
    } as ResourceMutation);
    queue.queue({
      op: "create",
      resource: "entities",
      body: { id: "new-ent" },
    } as ResourceMutation);

    await queue.flush();

    expect(calls.map((c) => c.method)).toEqual([
      "createEntity",
      "createAnnotation",
      "deleteAnnotation",
    ]);
    expect(queue.count).toBe(0);
    expect(queue.saveError).toBeNull();
  });

  it("marks the local annotation as persisted after a successful create", async () => {
    const { gateway } = makeGateway();
    const bbox = { persisted: false };
    const locator: LocalAnnotationLocator = {
      findLocalAnnotation: (localAnnotationId) => (localAnnotationId === "lb-1" ? bbox : undefined),
    };
    const queue = new MutationQueue(gateway, makeSession(), locator);

    queue.queue({
      op: "create",
      resource: "bboxes",
      body: {},
      widgetId: "w-1",
      localAnnotationId: "lb-1",
    } as ResourceMutation);

    await queue.flush();
    expect(bbox.persisted).toBe(true);
  });

  it("surfaces ApiError detail in saveError", async () => {
    const apiErr = new ApiError(
      "createAnnotation(bboxes) failed with 422 Unprocessable",
      422,
      '{"detail":"bad"}',
    );
    const { gateway } = makeGateway({ failOn: "createAnnotation", error: apiErr });
    const queue = new MutationQueue(gateway, makeSession(), noopLocator);

    queue.queue({ op: "create", resource: "bboxes", body: {} } as ResourceMutation);

    await queue.flush();

    expect(queue.saveError).toContain("createAnnotation(bboxes) failed with 422");
    expect(queue.saveError).toContain('{"detail":"bad"}');
    expect(queue.saving).toBe(false);
  });

  it("drops already-applied mutations so a retry does not re-send them", async () => {
    const apiErr = new ApiError(
      "createAnnotation(bboxes) failed with 422 Unprocessable",
      422,
      '{"detail":"bad"}',
    );
    const { gateway, calls } = makeGateway({ failOn: "createAnnotation", error: apiErr });
    const queue = new MutationQueue(gateway, makeSession(), noopLocator);

    queue.queue({ op: "create", resource: "entities", body: {} } as ResourceMutation);
    queue.queue({ op: "create", resource: "bboxes", body: {} } as ResourceMutation);
    queue.queue({ op: "delete", resource: "bboxes", id: "x" } as ResourceMutation);

    await queue.flush();

    // createEntity ran first (sort order) and succeeded; createAnnotation(bboxes) failed.
    expect(calls.map((c) => c.method)).toEqual(["createEntity", "createAnnotation"]);
    // createEntity was dropped; createBBox and deleteBBox remain for retry.
    expect(queue.count).toBe(2);
  });

  it("ignores re-entrant flush calls while saving", async () => {
    let resolveCreate!: () => void;
    const inflight = new Promise<void>((r) => (resolveCreate = r));

    const gateway: MutationGateway = {
      createEntity: async () => {
        await inflight;
        return {};
      },
      deleteEntity: () => Promise.resolve(),
      createAnnotation: () => Promise.resolve({}),
      updateAnnotation: () => Promise.resolve({}),
      deleteAnnotation: () => Promise.resolve(),
    };

    const queue = new MutationQueue(gateway, makeSession(), noopLocator);
    queue.queue({ op: "create", resource: "entities", body: {} } as ResourceMutation);

    const first = queue.flush();
    expect(queue.saving).toBe(true);

    // Second call returns immediately because we're already saving.
    const second = queue.flush();
    await second;
    expect(queue.saving).toBe(true); // first hasn't finished

    resolveCreate();
    await first;
    expect(queue.saving).toBe(false);
  });
});

describe("MutationQueue.dropForLocalAnnotation", () => {
  it("removes every queued mutation referencing the given local bbox id", () => {
    const { gateway } = makeGateway();
    const queue = new MutationQueue(gateway, makeSession(), noopLocator);

    queue.queue({
      op: "create",
      resource: "bboxes",
      body: {},
      localAnnotationId: "lb-doomed",
    } as ResourceMutation);
    queue.queue({
      op: "update",
      resource: "bboxes",
      id: "x",
      body: {},
      localAnnotationId: "lb-doomed",
    } as ResourceMutation);
    queue.queue({
      op: "create",
      resource: "bboxes",
      body: {},
      localAnnotationId: "lb-keep",
    } as ResourceMutation);

    const dropped = queue.dropForLocalAnnotation("lb-doomed");

    expect(dropped).toHaveLength(2);
    expect(queue.count).toBe(1);
    expect(queue.pending[0].localAnnotationId).toBe("lb-keep");
  });
});

describe("dropPendingEntityCreate", () => {
  const entityCreate = (localAnnotationId: string, id: string): ResourceMutation => ({
    op: "create",
    resource: ENTITY_RESOURCE,
    body: { id },
    widgetId: "w1",
    localAnnotationId,
  });

  it("removes an entity create queued for the given annotation", () => {
    const { gateway } = makeGateway();
    const queue = new MutationQueue(gateway, makeSession(), noopLocator);
    queue.queue(entityCreate("a1", "ent-1"));

    queue.dropPendingEntityCreate("a1");

    expect(queue.pending).toHaveLength(0);
  });

  it("keeps the annotation's own pending update", () => {
    const { gateway } = makeGateway();
    const queue = new MutationQueue(gateway, makeSession(), noopLocator);
    queue.queue(entityCreate("a1", "ent-1"));
    queue.upsertUpdate({
      op: "update",
      resource: "bboxes",
      id: "a1",
      body: { x: 1 },
      widgetId: "w1",
      localAnnotationId: "a1",
    });

    queue.dropPendingEntityCreate("a1");

    // Narrower than `dropForLocalAnnotation` on purpose: a reassignment has no
    // business undoing a geometry edit made in the same breath.
    expect(queue.pending.map((m) => m.op)).toEqual(["update"]);
  });

  it("leaves another annotation's entity create alone", () => {
    const { gateway } = makeGateway();
    const queue = new MutationQueue(gateway, makeSession(), noopLocator);
    queue.queue(entityCreate("a1", "ent-1"));
    queue.queue(entityCreate("a2", "ent-2"));

    queue.dropPendingEntityCreate("a1");

    expect(queue.pending).toHaveLength(1);
    expect(queue.pending[0].localAnnotationId).toBe("a2");
  });
});

describe("MutationQueue — a request on the wire", () => {
  /** A gateway whose updates wait for the test, then fail or succeed. */
  function heldUpdates() {
    let release!: (outcome: Error | null) => void;
    const answered = new Promise<Error | null>((r) => (release = r));
    const { gateway } = makeGateway();
    gateway.updateAnnotation = async () => {
      const error = await answered;
      if (error) throw error;
      return {};
    };
    return { gateway, release };
  }

  const update = (body: Record<string, unknown>, widgetId = "w1") => ({
    op: "update" as const,
    resource: "bboxes",
    id: "b1",
    body,
    widgetId,
    localAnnotationId: "b1",
  });

  /** Where two edits made one after the other move the row. */
  const FIRST_COORDS = [0.1, 0.1, 0.2, 0.2];
  const SECOND_COORDS = [0.3, 0.3, 0.2, 0.2];

  it("queues a change of the row being sent after it, never into it", async () => {
    const { gateway, release } = heldUpdates();
    const queue = new MutationQueue(gateway, makeSession(), noopLocator);
    queue.upsertUpdate(update({ coords: FIRST_COORDS }));

    const flushing = queue.flush();
    queue.upsertUpdate(update({ coords: SECOND_COORDS }));
    expect(queue.count).toBe(2); // one on the wire, one waiting
    release(null);
    await flushing;

    expect(queue.pending).toEqual([update({ coords: SECOND_COORDS })]);
  });

  it("neither takes back nor reports a failed request of a queue reset meanwhile", async () => {
    const { gateway, release } = heldUpdates();
    const queue = new MutationQueue(gateway, makeSession(), noopLocator);
    queue.upsertUpdate(update({ coords: FIRST_COORDS }));

    const flushing = queue.flush();
    queue.reset(); // another record opened
    release(new Error("backend down"));
    await flushing;

    expect(queue.pending).toEqual([]);
    expect(queue.saveError).toBeNull();
  });

  it("records each write as it leaves, and undoes the record when it fails", async () => {
    const { gateway, release } = heldUpdates();
    const events: string[] = [];
    const locator: LocalAnnotationLocator = {
      findLocalAnnotation: () => undefined,
      recordWrite: (mutation) => {
        events.push(`record ${mutation.op}`);
        return () => events.push("undo");
      },
    };
    const queue = new MutationQueue(gateway, makeSession(), locator);
    queue.upsertUpdate(update({ coords: [0, 0, 1, 1] }));

    const flushing = queue.flush();
    expect(events).toEqual(["record update"]);
    release(new Error("backend down"));
    await flushing;

    expect(events).toEqual(["record update", "undo"]);
    // Back at the head of the queue, for the next save.
    expect(queue.pending).toEqual([update({ coords: [0, 0, 1, 1] })]);
  });
});

describe("MutationQueue — the locator told of each body queued", () => {
  /** A locator recording the body of each mutation it is told of, as the queue then holds it. */
  function recordingLocator() {
    const bodies: unknown[] = [];
    const locator: LocalAnnotationLocator = {
      findLocalAnnotation: () => undefined,
      recordQueued: (mutation) => {
        bodies.push(mutation.op === "delete" ? null : { ...mutation.body });
      },
    };
    return { locator, bodies };
  }

  const create = (body: Record<string, unknown>): ResourceMutation => ({
    op: "create",
    resource: "bboxes",
    body: { id: "b1", ...body },
    localAnnotationId: "b1",
  });

  it("is told of a mutation queued, and of a queued body a later gesture rewrites", () => {
    const { gateway } = makeGateway();
    const { locator, bodies } = recordingLocator();
    const queue = new MutationQueue(gateway, makeSession(), locator);

    queue.queue(create({ coords: [0, 0, 1, 1] }));
    queue.patchPendingCreate("b1", "bboxes", { coords: [0.5, 0.5, 1, 1] });
    queue.upsertUpdate({ op: "update", resource: "bboxes", id: "b2", body: { coords: [1] } });
    queue.upsertUpdate({ op: "update", resource: "bboxes", id: "b2", body: { coords: [2] } });

    expect(bodies).toEqual([
      { id: "b1", coords: [0, 0, 1, 1] },
      { id: "b1", coords: [0.5, 0.5, 1, 1] },
      { coords: [1] },
      { coords: [2] },
    ]);
  });
});

describe("MutationQueue — what a save reports", () => {
  it("clears the error of a failed save once nothing is left of it", async () => {
    const { gateway } = makeGateway({ failOn: "createAnnotation" });
    const queue = new MutationQueue(gateway, makeSession(), noopLocator);
    queue.queue({
      op: "create",
      resource: "bboxes",
      body: { id: "d1" },
      localAnnotationId: "d1",
    });
    await queue.flush();
    expect(queue.saveError).not.toBeNull();

    queue.dropForLocalAnnotation("d1"); // the draft is deleted
    await queue.flush();

    expect(queue.saveError).toBeNull();
  });

  it("gives an update to the gesture that last wrote its body", () => {
    const { gateway } = makeGateway();
    const queue = new MutationQueue(gateway, makeSession(), noopLocator);

    queue.upsertUpdate({ op: "update", resource: "bboxes", id: "b1", body: {}, widgetId: "panel" });
    queue.upsertUpdate({
      op: "update",
      resource: "bboxes",
      id: "b1",
      body: {},
      widgetId: "canvas",
    });

    expect(queue.pending.map((m) => m.widgetId)).toEqual(["canvas"]);
  });
});

describe("MutationQueue — what reached the server, over the HTTP gateway", () => {
  /** The statuses of a refusal — a busy dataset — and of a proxy's failure, which may come after a write. */
  const HTTP_CONFLICT = 409;
  const HTTP_BAD_GATEWAY = 502;

  afterEach(() => vi.unstubAllGlobals());

  /** Make the server answer every request with `status`. */
  function answerWith(status: number): void {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response(JSON.stringify({ detail: "x" }), { status }))),
    );
  }

  const deletes: [string, ResourceMutation][] = [
    ["an annotation delete", { op: "delete", resource: "bboxes", id: "b1" }],
    ["an entity delete", { op: "delete", resource: ENTITY_RESOURCE, id: "e1" }],
  ];

  it.each(deletes)(
    "%s the server refuses reached nothing; one a proxy fails may have",
    async (_write, mutation) => {
      const queue = new MutationQueue(httpDatasetGateway, makeSession(), noopLocator);
      queue.queue(mutation);

      answerWith(HTTP_CONFLICT);
      await queue.flush();
      expect(queue.saveError).toContain(String(HTTP_CONFLICT));
      expect(queue.writesLanded).toBe(0);

      answerWith(HTTP_BAD_GATEWAY);
      await queue.flush();
      expect(queue.writesLanded).toBe(1);
    },
  );
});
