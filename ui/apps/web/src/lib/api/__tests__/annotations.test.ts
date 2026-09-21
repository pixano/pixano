/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createAnnotation,
  createEntity,
  deleteAnnotation,
  deleteEntity,
  listAnnotations,
  listEntities,
  updateAnnotation,
} from "../annotations";
import type { BBox3DRow, BBoxRow } from "../annotations";
import { ApiError } from "../apiClient";

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
    vi.mocked(fetch).mockResolvedValueOnce(okJson({ items: [], total: 0, limit: 50, offset: 0 }));

    await listEntities(DS, { recordId: "rec-1", limit: 50 });

    const url = vi.mocked(fetch).mock.calls[0][0] as string;
    expect(url).toContain("record_id=rec-1");
    expect(url).toContain("limit=50");
    expect(url).toContain(`/datasets/${DS}/entities`);
  });

  it("defaults limit to 1000 when not specified", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(okJson({ items: [], total: 0, limit: 1000, offset: 0 }));

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

// ─── listAnnotations ─────────────────────────────────────────────────────────
// One function serves every annotation table, so the cases below exercise it
// through two different resources rather than through two functions.

describe("listAnnotations", () => {
  it("returns items from paginated response", async () => {
    const bboxes = [
      {
        id: "b1",
        record_id: "r1",
        entity_id: "e1",
        view_id: "v1",
        coords: [0, 0, 1, 1],
        format: "xywh",
        is_normalized: true,
      },
    ];
    vi.mocked(fetch).mockResolvedValueOnce(
      okJson({ items: bboxes, total: 1, limit: 1000, offset: 0 }),
    );

    const result = await listAnnotations<BBoxRow>(DS, "bboxes", { recordId: "r1" });
    expect(result).toEqual(bboxes);
  });

  it("targets the resource it is given", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(okJson({ items: [], total: 0, limit: 1000, offset: 0 }));

    await listAnnotations(DS, "masks", {});

    const url = vi.mocked(fetch).mock.calls[0][0] as string;
    expect(url).toContain(`/datasets/${DS}/masks`);
  });

  it("maps viewId to view_name query param", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(okJson({ items: [], total: 0, limit: 1000, offset: 0 }));

    await listAnnotations(DS, "bboxes", { viewId: "cam-front" });

    const url = vi.mocked(fetch).mock.calls[0][0] as string;
    expect(url).toContain("view_name=cam-front");
  });

  it("omits view_name when viewId is absent", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(okJson({ items: [], total: 0, limit: 1000, offset: 0 }));

    await listAnnotations(DS, "bboxes", {});

    const url = vi.mocked(fetch).mock.calls[0][0] as string;
    expect(url).not.toContain("view_name");
  });

  it("carries 3D rows through unchanged", async () => {
    const bboxes3d = [
      {
        id: "b3d-1",
        record_id: "r1",
        entity_id: "e1",
        view_id: "v1",
        coords: [0, 0, 0, 1, 1, 1],
        format: "xyzwhd",
        rotation: [1, 0, 0, 0, 1, 0, 0, 0, 1],
        is_normalized: false,
      },
    ];
    vi.mocked(fetch).mockResolvedValueOnce(
      okJson({ items: bboxes3d, total: 1, limit: 1000, offset: 0 }),
    );

    const result = await listAnnotations<BBox3DRow>(DS, "bbox3ds", { viewId: "lidar" });
    expect(result).toEqual(bboxes3d);
    expect(vi.mocked(fetch).mock.calls[0][0] as string).toContain(`/datasets/${DS}/bbox3ds`);
  });

  it("returns empty array when items is null", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      okJson({ items: null, total: 0, limit: 1000, offset: 0 }),
    );
    expect(await listAnnotations(DS, "bbox3ds", {})).toEqual([]);
  });

  it("throws ApiError on HTTP error", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(errResponse(500, "Server Error"));
    await expect(listAnnotations(DS, "bboxes", {})).rejects.toBeInstanceOf(ApiError);
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

// ─── createAnnotation ────────────────────────────────────────────────────────

describe("createAnnotation", () => {
  it("POSTs to the given resource endpoint", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(okJson({ id: "new-b" }));

    await createAnnotation(DS, "bboxes", { entity_id: "e1" });

    const [url, init] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`/datasets/${DS}/bboxes`);
    expect(init.method).toBe("POST");
  });
});

// ─── updateAnnotation ────────────────────────────────────────────────────────

describe("updateAnnotation", () => {
  it("PUTs to resource/:id and strips the id field from the body", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(okJson({ id: "b1", coords: [0, 0, 0.5, 0.5] }));

    await updateAnnotation(DS, "bboxes", "b1", { id: "b1", coords: [0, 0, 0.5, 0.5] });

    const [url, init] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`/datasets/${DS}/bboxes/b1?prune_orphan_entity=true`);
    expect(init.method).toBe("PUT");
    const sent = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(sent).not.toHaveProperty("id");
    expect(sent).toMatchObject({ coords: [0, 0, 0.5, 0.5] });
  });

  it("URL-encodes the annotation id", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(okJson({}));

    await updateAnnotation(DS, "bboxes", "a/b c", {});

    const [url] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    expect(url).toContain("a%2Fb%20c");
  });
});

// ─── deleteAnnotation ────────────────────────────────────────────────────────

describe("deleteAnnotation", () => {
  it("DELETEs the annotation by resource and id, asking the backend to prune an orphan entity", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 204 }));

    await deleteAnnotation(DS, "bboxes", "b1");

    const [url, init] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`/datasets/${DS}/bboxes/b1?prune_orphan_entity=true`);
    expect((init as RequestInit).method).toBe("DELETE");
  });

  it("does not throw on 404 (already deleted)", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 404 }));
    await expect(deleteAnnotation(DS, "bboxes", "gone")).resolves.toBeUndefined();
  });

  it("throws on unexpected non-404 error", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(null, { status: 500, statusText: "Internal Server Error" }),
    );
    await expect(deleteAnnotation(DS, "bboxes", "b1")).rejects.toThrow(
      "deleteAnnotation(bboxes) failed with 500",
    );
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
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(null, { status: 403, statusText: "Forbidden" }),
    );
    await expect(deleteEntity(DS, "e1")).rejects.toThrow("deleteEntity failed with 403");
  });
});
