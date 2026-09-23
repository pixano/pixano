/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { createCurrentItemSaveCoordinatorController } from "../currentItemSaveCoordinator";

describe("currentItemSaveCoordinator", () => {
  it("resolves immediately when the item is clean", async () => {
    const coordinator = createCurrentItemSaveCoordinatorController();

    await expect(coordinator.requestSave()).resolves.toEqual({ ok: true });
    expect(coordinator.value.status).toBe("idle");
    expect(coordinator.value.activeRequestId).toBeNull();
  });

  it("deduplicates concurrent save requests and resolves them after success", async () => {
    const coordinator = createCurrentItemSaveCoordinatorController();
    coordinator.syncDirty(true);

    const firstRequest = coordinator.requestSave();
    const secondRequest = coordinator.requestSave();

    expect(firstRequest).toBe(secondRequest);
    expect(coordinator.value.status).toBe("saving");
    expect(coordinator.value.activeRequestId).toBe(1);

    coordinator.setSaveSucceeded(1);

    await expect(firstRequest).resolves.toEqual({ ok: true });
    expect(coordinator.value.isDirty).toBe(false);
    expect(coordinator.value.status).toBe("idle");
    expect(coordinator.value.activeRequestId).toBeNull();
  });

  it("keeps the item dirty and reports failure when persistence fails", async () => {
    const coordinator = createCurrentItemSaveCoordinatorController();
    coordinator.syncDirty(true);

    const saveRequest = coordinator.requestSave();

    coordinator.setSaveFailed("Custom failure", 1);

    await expect(saveRequest).resolves.toEqual({ ok: false });
    expect(coordinator.value.isDirty).toBe(true);
    expect(coordinator.value.status).toBe("failed");
    expect(coordinator.value.errorMessage).toBe("Custom failure");
    expect(coordinator.value.activeRequestId).toBeNull();
  });

  it("preserves the save request while dirty sync drops to false during persistence", async () => {
    const coordinator = createCurrentItemSaveCoordinatorController();
    coordinator.syncDirty(true);

    const saveRequest = coordinator.requestSave();
    coordinator.syncDirty(false);

    expect(coordinator.value.isDirty).toBe(false);
    expect(coordinator.value.status).toBe("saving");
    expect(coordinator.value.activeRequestId).toBe(1);

    coordinator.setSaveSucceeded(1);

    await expect(saveRequest).resolves.toEqual({ ok: true });
  });

  it("resets pending requests when the current item changes", async () => {
    const coordinator = createCurrentItemSaveCoordinatorController();
    coordinator.syncDirty(true);

    const saveRequest = coordinator.requestSave();
    coordinator.resetForItemChange();

    await expect(saveRequest).resolves.toEqual({ ok: false });
    expect(coordinator.value).toEqual({
      isDirty: false,
      status: "idle",
      errorMessage: null,
      activeRequestId: null,
    });
  });
  it("keeps deduplicating while the queue's last request is still completing", async () => {
    const coordinator = createCurrentItemSaveCoordinatorController();
    coordinator.syncDirty(true);
    const saving = coordinator.requestSave();
    coordinator.syncDirty(false);
    expect(coordinator.requestSave()).toBe(saving);
    coordinator.setSaveSucceeded(1);
    await expect(saving).resolves.toEqual({ ok: true });
  });

  it("ignores completions from a previous record, with and without a new request", async () => {
    const coordinator = createCurrentItemSaveCoordinatorController();
    coordinator.syncDirty(true);
    const oldRequest = coordinator.requestSave();
    coordinator.resetForItemChange();
    await expect(oldRequest).resolves.toEqual({ ok: false });
    coordinator.syncDirty(true);
    coordinator.setSaveSucceeded(1);
    coordinator.setSaveFailed("Old failure", 1);
    expect(coordinator.value).toMatchObject({ isDirty: true, status: "idle", errorMessage: null });
    const newRequest = coordinator.requestSave();
    coordinator.setSaveSucceeded(1);
    coordinator.setSaveFailed("Old failure", 1);
    expect(coordinator.value).toMatchObject({ status: "saving", activeRequestId: 2 });
    coordinator.setSaveSucceeded(2);
    await expect(newRequest).resolves.toEqual({ ok: true });
  });

  it("does not authorize leaving while a newer edit is dirty", async () => {
    const coordinator = createCurrentItemSaveCoordinatorController();
    coordinator.syncDirty(true);
    const request = coordinator.requestSave();
    coordinator.setSaveSucceeded(1, true);
    await expect(request).resolves.toEqual({ ok: false });
    expect(coordinator.value.isDirty).toBe(true);
  });
});
