/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../apiClient";
import { getDataset, listDatasets, listRecords } from "../datasets";

const mockDatasetInfoResponse = {
  id: "ds-1",
  name: "COCO 2017",
  description: "Common Objects in Context",
  size: "18GB",
  preview: "",
  workspace: "image",
  storage_mode: "local",
  num_records: 5000,
};

const mockDatasetResponse = {
  id: "ds-1",
  path: "/data/ds-1",
  previews_path: "/previews/ds-1",
  thumbnail: "",
  tables: { records: "Record" },
  feature_values: {},
  info: mockDatasetInfoResponse,
};

const mockPaginatedRecords = {
  items: [
    { id: "rec-1", split: "train" },
    { id: "rec-2", split: "val" },
  ],
  total: 2,
  limit: 50,
  offset: 0,
};

function okResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function errorResponse(status: number, statusText: string, detail: string): Response {
  return new Response(JSON.stringify({ detail }), {
    status,
    statusText,
    headers: { "Content-Type": "application/json" },
  });
}

describe("listDatasets", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("returns mapped DatasetInfo array on success", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(okResponse([mockDatasetInfoResponse]));

    const result = await listDatasets();

    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({
      id: "ds-1",
      name: "COCO 2017",
      num_items: 5000,
    });
  });

  it("returns empty array when server returns empty list", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(okResponse([]));

    const result = await listDatasets();

    expect(result).toEqual([]);
  });

  it("returns empty array (fallback) on HTTP error", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(errorResponse(500, "Internal Server Error", "crash"));

    const result = await listDatasets();

    expect(result).toEqual([]);
  });

  it("returns empty array (fallback) on network error", async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new Error("Network failure"));

    const result = await listDatasets();

    expect(result).toEqual([]);
  });

  it("calls /datasets endpoint", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(okResponse([]));

    await listDatasets();

    expect(fetch).toHaveBeenCalledWith("/datasets", {});
  });
});

describe("getDataset", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("returns Dataset with correct id on success", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(okResponse(mockDatasetResponse));

    const result = await getDataset("ds-1");

    expect(result.id).toBe("ds-1");
  });

  it("calls /datasets/{id} endpoint", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(okResponse(mockDatasetResponse));

    await getDataset("ds-1");

    expect(fetch).toHaveBeenCalledWith("/datasets/ds-1", {});
  });

  it("throws ApiError on HTTP 404", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(errorResponse(404, "Not Found", "Dataset not found"));

    await expect(getDataset("missing")).rejects.toBeInstanceOf(ApiError);
  });

  it("preserves status code in thrown ApiError", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(errorResponse(403, "Forbidden", "Access denied"));

    await expect(getDataset("ds-1")).rejects.toMatchObject({
      name: "ApiError",
      status: 403,
    });
  });
});

describe("listRecords", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("returns paginated records on success", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(okResponse(mockPaginatedRecords));

    const result = await listRecords("ds-1");

    expect(result.items).toHaveLength(2);
    expect(result.items[0].id).toBe("rec-1");
    expect(result.total).toBe(2);
  });

  it("uses default limit=50 and offset=0 in URL", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(okResponse(mockPaginatedRecords));

    await listRecords("ds-1");

    expect(fetch).toHaveBeenCalledWith(
      "/datasets/ds-1/records?limit=50&offset=0&include=view_previews",
      {},
    );
  });

  it("passes custom limit and offset in URL", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      okResponse({ ...mockPaginatedRecords, limit: 10, offset: 20 }),
    );

    await listRecords("ds-1", 10, 20);

    expect(fetch).toHaveBeenCalledWith(
      "/datasets/ds-1/records?limit=10&offset=20&include=view_previews",
      {},
    );
  });

  it("encodes the dataset id in the URL", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(okResponse(mockPaginatedRecords));

    await listRecords("my-dataset-42");

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/datasets/my-dataset-42/records"),
      {},
    );
  });

  it("throws ApiError on HTTP 404", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(errorResponse(404, "Not Found", "Dataset not found"));

    await expect(listRecords("missing")).rejects.toBeInstanceOf(ApiError);
  });

  it("preserves status and body in thrown ApiError", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(errorResponse(500, "Internal Server Error", "crash"));

    await expect(listRecords("ds-1")).rejects.toMatchObject({
      name: "ApiError",
      status: 500,
    });
  });
});
