/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  analyzeImportSource,
  browseServerFolders,
  cancelIoJob,
  getIoJob,
  listIoFormats,
  startIoImport,
} from "../ioApi";

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

describe("ioApi", () => {
  it("lists formats", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse([{ name: "coco", title: "COCO", can_import: true }]),
    );
    await expect(listIoFormats()).resolves.toMatchObject([{ name: "coco" }]);
    expect(fetchMock).toHaveBeenCalledWith("/io/formats", expect.anything());
  });

  it("browses server folders with an encoded path (empty = home)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ path: "/home/me", parent: "/home", entries: [] }),
    );
    await expect(browseServerFolders()).resolves.toMatchObject({ path: "/home/me" });
    expect(fetchMock).toHaveBeenCalledWith("/io/browse", expect.anything());
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ path: "/data/my sets", parent: "/data", entries: [] }),
    );
    await browseServerFolders("/data/my sets");
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/io/browse?path=%2Fdata%2Fmy%20sets",
      expect.anything(),
    );
  });

  it("analyzes with a source + spec body", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ format: "coco", plan_id: "p1", totals: { records: 3 } }),
    );
    const plan = await analyzeImportSource("/data/src", { format: "coco" });
    expect(plan.plan_id).toBe("p1");
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      source: "/data/src",
      spec: { format: "coco" },
    });
  });

  it("starts an import (202) and returns the job", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ job_id: "j1", status: "pending" }, 202));
    const job = await startIoImport({ plan_id: "p1", source: "/data/src" });
    expect(job.job_id).toBe("j1");
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({
      plan_id: "p1",
      source: "/data/src",
      spec: {},
    });
  });

  it("polls a job", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ job_id: "j1", status: "running", progress: { done: 5 } }),
    );
    await expect(getIoJob("j1")).resolves.toMatchObject({ status: "running" });
    expect(fetchMock).toHaveBeenCalledWith("/io/jobs/j1", expect.anything());
  });

  it("cancels with POST (not DELETE)", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ job_id: "j1", status: "running" }));
    await cancelIoJob("j1");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/io/jobs/j1/cancel");
    expect(init.method).toBe("POST");
  });

  it("propagates ApiError with status and body", async () => {
    fetchMock.mockResolvedValueOnce(new Response("plan not found", { status: 409 }));
    await expect(startIoImport({ plan_id: "ghost", source: "/x" })).rejects.toMatchObject({
      name: "ApiError",
      status: 409,
    });
  });
});
