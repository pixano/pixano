/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../apiClient";
import {
  createBBox,
  createEntity,
  deleteBBox,
  deleteEntity,
  listBBox3Ds,
  listBBoxes,
  listEntities,
  updateBBox,
} from "../annotations";

// ─── Helpers ────────────────────────────────────────────────────────────────

function okJson(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function errResponse(status: number, statusText: string): Response {
  return new Response(JSON.stringify({ detail: statusText }), {
    status,
    statusText,
    headers: { "Content-Type": "application/json" },
  });
}

const DS = "ds-abc";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

// ─── listEntities ────────────────────────────────────────────────────────────

describe("listEntities", () => {
  it("returns items from paginated response", async () => {
    const entities = [{ id: "e1", record_id: "r1" }];
    vi.mocked(fetch).mockResolvedValueOnce(
      okJson({ items: entities, total: 1, limit: 1000, offset: 0 }),
    );

    const result = await listEntities(DS, { recordId: "r1" });

    expect(result).toEqual(entities);
  });

  it("includes record_id and limit in query string", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      okJson({ items: [], total: 0, limit: 50, offset: 0 }),
    );

    await listEntities(DS, { recordId: "rec-1", limit: 50 });

    const url = vi.mocked(fetch).mock.calls[0][0] as string;
    expect(url).toContain("record_id=rec-1");
    expect(url).toContain("limit=50");
    expect(url).toContain(`/datasets/${DS}/entities`);
  });

  it("defaults limit to 1000 when not specified", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      okJson({ items: [], total: 0, limit: 1000, offset: 0 }),
    );

    await listEntities(DS);

    const url = vi.mocked(fetch).mock.calls[0][0] as string;
    expect(url).toContain("limit=1000");
  });

  it("returns empty array when items is missing", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      okJson({ items: null, total: 0, limit: 1000, offset: 0 }),
    );

    const result = await listEntities(DS);
    expect(result).toEqual([]);
  });

  it("throws ApiError on HTTP error", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(errResponse(404, "Not Found"));

    await expect(listEntities(DS)).rejects.toBeInstanceOf(ApiError);
  });
});

// ─── listBBoxes ──────────────────────────────────────────────────────────────

describe("listBBoxes", () => {
  it("returns items from paginated response", async () => {
    const bboxes = [
      { id: "b1", record_id: "r1", entity_id: "e1", view_id: "v1", coords: [0, 0, 1, 1], format: "xywh", is_normalized: true },
    ];
    vi.mocked(fetch).mockResolvedValueOnce(
      okJson({ items: bboxes, total: 1, limit: 1000, offset: 0 }),
    );

    const result = await listBBoxes(DS, { recordId: "r1" });
    expect(result).toEqual(bboxes);
  });

  it("maps viewId to view_name query param", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      okJson({ items: [], total: 0, limit: 1000, offset: 0 }),
    );

    await listBBoxes(DS, { viewId: "cam-front" });

    const url = vi.mocked(fetch).mock.calls[0][0] as string;
    expect(url).toContain("view_name=cam-front");
  });

  it("omits view_name when viewId is absent", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      okJson({ items: [], total: 0, limit: 1000, offset: 0 }),
    );

    await listBBoxes(DS);

    const url = vi.mocked(fetch).mock.calls[0][0] as string;
    expect(url).not.toContain("view_name");
  });

  it("throws ApiError on HTTP error", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(errResponse(500, "Server Error"));
    await expect(listBBoxes(DS)).rejects.toBeInstanceOf(ApiError);
  });
});

// ─── listBBox3Ds ─────────────────────────────────────────────────────────────

describe("listBBox3Ds", () => {
  it("returns items from paginated response", async () => {
    const bboxes3d = [
      {
        id: "b3d-1", record_id: "r1", entity_id: "e1", view_id: "v1",
        coords: [0, 0, 0, 1, 1, 1], format: "xyzwhd", rotation: [1,0,0,0,1,0,0,0,1], is_normalized: false,
      },
    ];
    vi.mocked(fetch).mockResolvedValueOnce(
      okJson({ items: bboxes3d, total: 1, limit: 1000, offset: 0 }),
    );

    const result = await listBBox3Ds(DS, { recordId: "r1" });
    expect(result).toEqual(bboxes3d);
  });

  it("maps viewId to view_name param", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      okJson({ items: [], total: 0, limit: 1000, offset: 0 }),
    );

    await listBBox3Ds(DS, { viewId: "lidar" });

    const url = vi.mocked(fetch).mock.calls[0][0] as string;
    expect(url).toContain("view_name=lidar");
    expect(url).toContain(`/datasets/${DS}/bbox3ds`);
  });

  it("returns empty array when items is null", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      okJson({ items: null, total: 0, limit: 1000, offset: 0 }),
    );
    expect(await listBBox3Ds(DS)).toEqual([]);
  });
});

// ─── createEntity ────────────────────────────────────────────────────────────

describe("createEntity", () => {
  it("POSTs to the entities endpoint and returns the created row", async () => {
    const created = { id: "new-e", record_id: "r1" };
    vi.mocked(fetch).mockResolvedValueOnce(okJson(created));

    const result = await createEntity(DS, { record_id: "r1" });

    expect(result).toEqual(created);
    const [url, init] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`/datasets/${DS}/entities`);
    expect(init.method).toBe("POST");
  });

  it("throws ApiError on 422", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(errResponse(422, "Unprocessable"));
    await expect(createEntity(DS, {})).rejects.toBeInstanceOf(ApiError);
  });
});

// ─── createBBox ──────────────────────────────────────────────────────────────

describe("createBBox", () => {
  it("POSTs to bboxes endpoint", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(okJson({ id: "new-b" }));

    await createBBox(DS, { entity_id: "e1" });

    const [url, init] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`/datasets/${DS}/bboxes`);
    expect(init.method).toBe("POST");
  });
});

// ─── updateBBox ──────────────────────────────────────────────────────────────

describe("updateBBox", () => {
  it("PUTs to bboxes/:id and strips the id field from the body", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(okJson({ id: "b1", coords: [0, 0, 0.5, 0.5] }));

    await updateBBox(DS, "b1", { id: "b1", coords: [0, 0, 0.5, 0.5] });

    const [url, init] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`/datasets/${DS}/bboxes/b1`);
    expect(init.method).toBe("PUT");
    // id must be stripped from the patch body
    const sent = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(sent).not.toHaveProperty("id");
    expect(sent).toMatchObject({ coords: [0, 0, 0.5, 0.5] });
  });

  it("URL-encodes the bbox id", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(okJson({}));

    await updateBBox(DS, "a/b c", {});

    const [url] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    expect(url).toContain("a%2Fb%20c");
  });
});

// ─── deleteBBox ──────────────────────────────────────────────────────────────

describe("deleteBBox", () => {
  it("DELETEs the bbox by id", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 204 }));

    await deleteBBox(DS, "b1");

    const [url, init] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`/datasets/${DS}/bboxes/b1`);
    expect((init as RequestInit).method).toBe("DELETE");
  });

  it("does not throw on 404 (already deleted)", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 404 }));
    await expect(deleteBBox(DS, "gone")).resolves.toBeUndefined();
  });

  it("throws on unexpected non-404 error", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 500, statusText: "Internal Server Error" }));
    await expect(deleteBBox(DS, "b1")).rejects.toThrow("deleteBBox failed with 500");
  });
});

// ─── deleteEntity ────────────────────────────────────────────────────────────

describe("deleteEntity", () => {
  it("DELETEs the entity by id", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 204 }));

    await deleteEntity(DS, "e1");

    const [url, init] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`/datasets/${DS}/entities/e1`);
    expect((init as RequestInit).method).toBe("DELETE");
  });

  it("does not throw on 404", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 404 }));
    await expect(deleteEntity(DS, "gone")).resolves.toBeUndefined();
  });

  it("throws on unexpected error", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 403, statusText: "Forbidden" }));
    await expect(deleteEntity(DS, "e1")).rejects.toThrow("deleteEntity failed with 403");
  });
});
