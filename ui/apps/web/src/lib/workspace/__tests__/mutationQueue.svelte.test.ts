/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import type { ResourceMutation } from "$lib/annotations/types.js";
import { ApiError } from "$lib/api/apiClient.js";

import type { MutationGateway } from "../datasetGateway.js";
import { MutationQueue, type LocalBBoxLocator } from "../mutationQueue.svelte.js";
import { WorkspaceSession } from "../workspaceSession.svelte.js";

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

const noopLocator: LocalBBoxLocator = {
  findLocalBBox: () => undefined,
};

// ─── Tests ──────────────────────────────────────────────────────────────────

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

  it("marks the LocalBBox as persisted after a successful create", async () => {
    const { gateway } = makeGateway();
    const bbox = { persisted: false };
    const locator: LocalBBoxLocator = {
      findLocalBBox: (widgetId, localBBoxId) =>
        widgetId === "w-1" && localBBoxId === "lb-1" ? bbox : undefined,
    };
    const queue = new MutationQueue(gateway, makeSession(), locator);

    queue.queue({
      op: "create",
      resource: "bboxes",
      body: {},
      widgetId: "w-1",
      localBBoxId: "lb-1",
    } as ResourceMutation);

    await queue.flush();
    expect(bbox.persisted).toBe(true);
  });

  it("surfaces ApiError detail in saveError", async () => {
    const apiErr = new ApiError("createAnnotation(bboxes) failed with 422 Unprocessable", 422, '{"detail":"bad"}');
    const { gateway } = makeGateway({ failOn: "createAnnotation", error: apiErr });
    const queue = new MutationQueue(gateway, makeSession(), noopLocator);

    queue.queue({ op: "create", resource: "bboxes", body: {} } as ResourceMutation);

    await queue.flush();

    expect(queue.saveError).toContain("createAnnotation(bboxes) failed with 422");
    expect(queue.saveError).toContain('{"detail":"bad"}');
    expect(queue.saving).toBe(false);
  });

  it("drops already-applied mutations so a retry does not re-send them", async () => {
    const apiErr = new ApiError("createAnnotation(bboxes) failed with 422 Unprocessable", 422, '{"detail":"bad"}');
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

describe("MutationQueue.dropForLocalBBox", () => {
  it("removes every queued mutation referencing the given local bbox id", () => {
    const { gateway } = makeGateway();
    const queue = new MutationQueue(gateway, makeSession(), noopLocator);

    queue.queue({
      op: "create",
      resource: "bboxes",
      body: {},
      localBBoxId: "lb-doomed",
    } as ResourceMutation);
    queue.queue({
      op: "update",
      resource: "bboxes",
      id: "x",
      body: {},
      localBBoxId: "lb-doomed",
    } as ResourceMutation);
    queue.queue({
      op: "create",
      resource: "bboxes",
      body: {},
      localBBoxId: "lb-keep",
    } as ResourceMutation);

    const dropped = queue.dropForLocalBBox("lb-doomed");

    expect(dropped).toHaveLength(2);
    expect(queue.count).toBe(1);
    expect(queue.pending[0].localBBoxId).toBe("lb-keep");
  });
});
