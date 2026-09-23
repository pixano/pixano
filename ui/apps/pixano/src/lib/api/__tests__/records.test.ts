/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getNeighbors } from "../filters";
import { listRecords } from "../records";

const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const jsonResponse = (payload: unknown, status = 200) =>
  new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });

const emptyPage = { items: [], total: 0, limit: 20, offset: 0 };

function requestedUrl(): string {
  return fetchMock.mock.calls[0][0] as string;
}

describe("listRecords query building", () => {
  it("forwards repeated filter params, q, sort and order", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(emptyPage));
    await listRecords("ds", {
      filters: ["split:eq:train", "score:gte:0.5"],
      q: "dog",
      sort: "score",
      order: "desc",
      limit: 20,
      offset: 40,
    });
    const url = requestedUrl();
    expect(url).toContain("filter=split%3Aeq%3Atrain");
    expect(url).toContain("filter=score%3Agte%3A0.5");
    expect(url).toContain("q=dog");
    expect(url).toContain("sort=score");
    expect(url).toContain("order=desc");
    expect(url).toContain("offset=40");
    expect(url).toContain("include=view_previews");
  });

  it("omits empty optional params", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(emptyPage));
    await listRecords("ds", { limit: 20, offset: 0 });
    const url = requestedUrl();
    expect(url).not.toContain("filter=");
    expect(url).not.toContain("q=");
    expect(url).not.toContain("sort=");
  });

  it("still forwards a deprecated raw where clause", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(emptyPage));
    await listRecords("ds", { where: "split = 'train'" });
    expect(requestedUrl()).toContain("where=split");
  });
});

describe("getNeighbors query building", () => {
  it("forwards filter, sort and order to the neighbors endpoint", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ prev: "a", next: "c", position: 2, total: 3 }));
    const result = await getNeighbors("ds", "b", {
      filters: ["split:eq:train"],
      sort: "id",
      order: "asc",
    });
    const url = requestedUrl();
    expect(url).toContain("/datasets/ds/records/b/neighbors");
    expect(url).toContain("filter=split%3Aeq%3Atrain");
    expect(url).toContain("sort=id");
    expect(result).toEqual({ prev: "a", next: "c", position: 2, total: 3 });
  });
});
