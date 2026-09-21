/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ResourceMutation } from "../resourcePayloads";
import { persistSaveItems, saveErrorMessage } from "../saveOrchestration";
import { createSaveQueue } from "$lib/stores/saveQueue";

const fetchMock = vi.fn<typeof fetch>();
const response = (status = 201, detail?: unknown) =>
  new Response(status === 204 ? null : JSON.stringify({ detail }), { status });
const mutation = (
  resource: string,
  id: string,
  op: ResourceMutation["op"] = "create",
  body: Record<string, unknown> = {},
): ResourceMutation => ({
  op,
  target: { resource, id },
  table: resource.replaceAll("-", "_"),
  body: op === "delete" ? undefined : { id, ...body },
});

function deferredResponse() {
  let resolve!: (value: Response) => void;
  const promise = new Promise<Response>((done) => (resolve = done));
  return { promise, resolve };
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  vi.spyOn(console, "error").mockImplementation(() => {});
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const requests = () =>
  fetchMock.mock.calls.map(([url, init]) => ({
    url,
    method: init?.method,
    body:
      typeof init?.body === "string"
        ? (JSON.parse(init.body) as Record<string, unknown>)
        : undefined,
  }));

describe("resumable annotation saves", () => {
  it("acknowledges successful entities before retrying a failed annotation", async () => {
    const queue = createSaveQueue();
    queue.stage(mutation("bboxes", "box"));
    queue.stage(mutation("entities", "entity"));
    fetchMock.mockResolvedValueOnce(response()).mockResolvedValueOnce(response(503));
    await expect(persistSaveItems(queue, "ds")).rejects.toThrow();
    expect(queue.mutations.map((entry) => entry.target.id)).toEqual(["box"]);
    fetchMock.mockResolvedValueOnce(response());
    await persistSaveItems(queue, "ds");
    expect(requests().map(({ url }) => url)).toEqual([
      "/datasets/ds/entities",
      "/datasets/ds/bboxes",
      "/datasets/ds/bboxes",
    ]);
    expect(queue.mutations).toEqual([]);
  });

  it("replays an identical create after a lost response, then sends newer edits", async () => {
    const queue = createSaveQueue();
    queue.stage(mutation("entities", "entity", "create", { label: "first" }));
    const stored = new Map<string, string>();
    let loseResponse = true;
    fetchMock.mockImplementation((url, init) => {
      const body = typeof init?.body === "string" ? init.body : "";
      const requestUrl = typeof url === "string" ? url : url instanceof URL ? url.href : url.url;
      if (init?.method === "POST") {
        const existing = stored.get(requestUrl);
        if (existing && existing !== body)
          return Promise.resolve(response(409, { code: "id_conflict" }));
        stored.set(requestUrl, body);
        if (loseResponse) {
          loseResponse = false;
          return Promise.reject(new TypeError("Connection lost after commit"));
        }
      }
      return Promise.resolve(response());
    });
    await expect(persistSaveItems(queue, "ds")).rejects.toThrow("Connection lost");
    queue.stage(mutation("entities", "entity", "update", { label: "second" }));
    await persistSaveItems(queue, "ds");
    expect(requests().map(({ method, body }) => [method, body?.label])).toEqual([
      ["POST", "first"],
      ["POST", "first"],
      ["PUT", "second"],
    ]);
    expect(stored.size).toBe(1);
    expect(queue.mutations).toEqual([]);
  });

  it.each(["update", "delete"] as const)(
    "retains %s arriving while creation is in flight",
    async (op) => {
      const queue = createSaveQueue();
      queue.stage(mutation("entities", "entity"));
      const creating = deferredResponse();
      fetchMock.mockReturnValueOnce(creating.promise).mockResolvedValue(response());
      const saving = persistSaveItems(queue, "ds");
      queue.stage(mutation("entities", "entity", op, { label: "edited" }));
      queue.stage(mutation("entities", "another"));
      expect(queue.mutations).toHaveLength(3);
      creating.resolve(response());
      await saving;
      expect(requests()).toContainEqual(
        expect.objectContaining({
          url: "/datasets/ds/entities/entity",
          method: op === "update" ? "PUT" : "DELETE",
        }),
      );
      expect(requests()).toContainEqual(
        expect.objectContaining({
          method: "POST",
          body: { id: "another" },
        }),
      );
      expect(queue.mutations).toEqual([]);
    },
  );

  it("does not discard an edit arriving during an update", async () => {
    const queue = createSaveQueue();
    queue.stage(mutation("bboxes", "box", "update", { coords: [1, 2, 3, 4] }));
    const updating = deferredResponse();
    fetchMock.mockReturnValueOnce(updating.promise).mockResolvedValue(response());
    const saving = persistSaveItems(queue, "ds");
    queue.stage(mutation("bboxes", "box", "update", { coords: [4, 3, 2, 1] }));
    updating.resolve(response());
    await saving;
    expect(requests().map(({ body }) => body?.coords)).toEqual([
      [1, 2, 3, 4],
      [4, 3, 2, 1],
    ]);
  });

  it("replays an update whose response was lost before applying a later edit", async () => {
    const queue = createSaveQueue();
    queue.stage(mutation("entities", "entity", "update", { label: "first" }));
    fetchMock.mockRejectedValueOnce(new TypeError("Lost update response"));
    await expect(persistSaveItems(queue, "ds")).rejects.toThrow();
    queue.stage(mutation("entities", "entity", "update", { label: "second" }));
    fetchMock.mockResolvedValue(response());
    await persistSaveItems(queue, "ds");
    expect(requests().map(({ method, body }) => [method, body?.label])).toEqual([
      ["PUT", "first"],
      ["PUT", "first"],
      ["PUT", "second"],
    ]);
  });

  it.each([422, 409])(
    "rebases newer corrections after a definite rejection (%s)",
    async (status) => {
      const queue = createSaveQueue();
      queue.stage(mutation("bboxes", "box", "create", { coords: [1] }));
      const creating = deferredResponse();
      fetchMock.mockReturnValueOnce(creating.promise);
      const saving = persistSaveItems(queue, "ds");
      queue.stage(mutation("bboxes", "box", "update", { coords: [1, 2, 3, 4] }));
      creating.resolve(
        response(status, status === 409 ? { code: "dataset_busy" } : "Invalid coords"),
      );
      await expect(saving).rejects.toThrow();
      fetchMock.mockResolvedValueOnce(response());
      await persistSaveItems(queue, "ds");
      expect(requests().at(-1)).toMatchObject({ method: "POST", body: { coords: [1, 2, 3, 4] } });
    },
  );

  it("keeps a conflicting create explicit instead of overwriting the other row", async () => {
    const queue = createSaveQueue();
    queue.stage(mutation("entities", "entity", "create", { label: "ours" }));
    fetchMock.mockResolvedValueOnce(response(409, { code: "id_conflict" }));
    const error = await persistSaveItems(queue, "ds").catch((error: unknown) => error);
    expect(saveErrorMessage(error)).toContain("existing annotation has different data");
    queue.stage(mutation("entities", "entity", "update", { label: "newer" }));
    expect(queue.next()?.mutation).toMatchObject({ op: "create", body: { label: "ours" } });
  });

  it("snapshots nested data and cancels unsent create/delete pairs", async () => {
    const queue = createSaveQueue();
    const coords = [1, 2, 3, 4];
    queue.stage(mutation("bboxes", "box", "create", { coords }));
    coords[0] = 100;
    queue.stage(mutation("entities", "removed"));
    queue.stage(mutation("entities", "removed", "delete"));
    fetchMock.mockResolvedValue(response());
    await persistSaveItems(queue, "ds");
    expect(requests()).toHaveLength(1);
    expect(requests()[0].body?.coords).toEqual([1, 2, 3, 4]);
  });

  it("preserves restoration of an object whose deletion was rejected before writing", async () => {
    const queue = createSaveQueue();
    queue.stage(mutation("entities", "entity", "delete"));
    const deleting = deferredResponse();
    fetchMock.mockReturnValueOnce(deleting.promise);
    const saving = persistSaveItems(queue, "ds");
    queue.stage(mutation("entities", "entity", "create", { label: "restored" }));
    deleting.resolve(response(409, { code: "dataset_busy" }));
    await expect(saving).rejects.toThrow();
    fetchMock.mockResolvedValueOnce(response());
    await persistSaveItems(queue, "ds");
    expect(requests().at(-1)).toMatchObject({ method: "PUT", body: { label: "restored" } });
  });

  it("orders dependent deletes and accepts a delete whose prior response was lost", async () => {
    const queue = createSaveQueue();
    queue.stage(mutation("entities", "entity", "delete"));
    queue.stage(mutation("tracklets", "track", "delete"));
    queue.stage(mutation("bboxes", "box", "delete"));
    fetchMock.mockRejectedValueOnce(new TypeError("Lost delete response"));
    await expect(persistSaveItems(queue, "ds")).rejects.toThrow();
    fetchMock.mockResolvedValueOnce(response(404)).mockResolvedValue(response(204));
    await persistSaveItems(queue, "ds");
    expect(requests().map(({ url }) => url)).toEqual([
      "/datasets/ds/bboxes/box",
      "/datasets/ds/bboxes/box",
      "/datasets/ds/tracklets/track",
      "/datasets/ds/entities/entity",
    ]);
    expect(queue.mutations).toEqual([]);
  });

  it("ignores an old acknowledgement after the workspace queue is reset", async () => {
    const queue = createSaveQueue();
    queue.stage(mutation("entities", "old"));
    const creating = deferredResponse();
    fetchMock.mockReturnValueOnce(creating.promise);
    const saving = persistSaveItems(queue, "old-ds");
    queue.reset();
    queue.stage(mutation("entities", "new"));
    creating.resolve(response());
    await saving;
    expect(queue.mutations.map((entry) => entry.target.id)).toEqual(["new"]);
    expect(requests()).toHaveLength(1);
  });
});
