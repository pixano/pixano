/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getUiOptions } from "../uiOptions";

describe("getUiOptions", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("reports the new UI as the server exposes it", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ new_ui_enabled: true }), { status: 200 }),
    );

    await expect(getUiOptions()).resolves.toEqual({ new_ui_enabled: true });
    expect(fetch).toHaveBeenCalledWith("/app/ui", {});
  });

  it("keeps the new UI hidden when the server does not answer", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response("", { status: 404 }));

    await expect(getUiOptions()).resolves.toEqual({ new_ui_enabled: false });
  });

  it("keeps the new UI hidden when the request fails", async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new TypeError("network down"));

    await expect(getUiOptions()).resolves.toEqual({ new_ui_enabled: false });
  });
});
