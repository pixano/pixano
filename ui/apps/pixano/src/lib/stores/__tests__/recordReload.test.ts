/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it, vi } from "vitest";

const navigation = vi.hoisted(() => ({ invalidateAll: vi.fn() }));
vi.mock("$app/navigation", () => navigation);

const { recordReloads, reloadOpenRecord } = await import("../recordReload.svelte");

describe("reloadOpenRecord", () => {
  it("asks the workspace to show the record again once it has been read again", async () => {
    let read: () => void = () => undefined;
    navigation.invalidateAll.mockReturnValue(new Promise<void>((resolve) => (read = resolve)));
    const before = recordReloads.value;

    const reloading = reloadOpenRecord();
    expect(recordReloads.value).toBe(before);
    read();
    await reloading;

    expect(navigation.invalidateAll).toHaveBeenCalledTimes(1);
    expect(recordReloads.value).toBe(before + 1);
  });
});
