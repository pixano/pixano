/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it, vi } from "vitest";

import {
  createNavigationGuard,
  replayNavigation,
  saveBeforeNavigation,
  type GuardedNavigation,
} from "../navigationGuard";

const intent = (overrides: Partial<GuardedNavigation> = {}): GuardedNavigation => ({
  from: "http://localhost/#/explorer/ds/workspace/a",
  to: "http://localhost/#/",
  fromRecord: "ds/a",
  toRecord: null,
  type: "goto",
  willUnload: false,
  ...overrides,
});
const dirty = { isDirty: true, isSaving: false };

describe("global unsaved navigation guard", () => {
  it.each(["goto", "link", "popstate"])("guards dirty record departures via %s", (type) => {
    const guard = createNavigationGuard();
    const navigation = intent({ type, delta: type === "popstate" ? -1 : undefined });
    expect(guard.intercept(navigation, dirty)).toBe("block");
    expect(guard.pending).toEqual(navigation);
    guard.clear();
    expect(guard.pending).toBeNull();
    // Cancelling the dialog does not confer permission for a later departure.
    expect(guard.intercept(navigation, dirty)).toBe("block");
  });

  it("allows clean navigation and query changes within the same record", () => {
    const guard = createNavigationGuard();
    expect(guard.intercept(intent(), { isDirty: false, isSaving: false })).toBe("allow");
    expect(guard.intercept(intent({ toRecord: "ds/a" }), dirty)).toBe("allow");
    expect(guard.pending).toBeNull();
    expect(guard.intercept(intent({ toRecord: "ds/b" }), dirty)).toBe("block");
  });

  it("protects pending writes even during the clean queue's final acknowledgement", () => {
    const guard = createNavigationGuard();
    expect(guard.intercept(intent(), { isDirty: false, isSaving: true })).toBe("block");
  });

  it("requests native confirmation for refresh/close and external navigation", () => {
    const guard = createNavigationGuard();
    expect(guard.intercept(intent({ willUnload: true, type: "leave", to: "" }), dirty)).toBe(
      "unload",
    );
    expect(guard.intercept(intent({ willUnload: true, type: "link" }), dirty)).toBe("unload");
    expect(guard.pending).toBeNull();
  });

  it("authorizes only the confirmed discard destination and consumes permission once", () => {
    const guard = createNavigationGuard();
    const navigation = intent();
    guard.intercept(navigation, dirty);
    expect(guard.authorizeDiscard()).toBe(navigation);
    expect(guard.intercept(intent({ to: "http://localhost/#/another" }), dirty)).toBe("block");
    expect(guard.intercept(navigation, dirty)).toBe("allow");
    expect(guard.intercept(navigation, dirty)).toBe("block");
  });

  it("rearms after navigation failure and never bypasses an active save", () => {
    const guard = createNavigationGuard();
    const navigation = intent();
    guard.intercept(navigation, dirty);
    guard.authorizeDiscard();
    expect(guard.intercept(navigation, { ...dirty, isSaving: true })).toBe("block");
    guard.rearm();
    expect(guard.intercept(navigation, dirty)).toBe("block");
  });

  it("continues only after successful saving leaves the workspace clean", async () => {
    const guard = createNavigationGuard();
    const navigation = intent();
    guard.intercept(navigation, dirty);
    const replay = vi.fn().mockResolvedValue(undefined);
    await saveBeforeNavigation(
      guard,
      () => Promise.resolve({ ok: false }),
      () => true,
      replay,
    );
    expect(replay).not.toHaveBeenCalled();
    expect(guard.pending).toBe(navigation);
    await saveBeforeNavigation(
      guard,
      () => Promise.resolve({ ok: true }),
      () => true,
      replay,
    );
    expect(replay).not.toHaveBeenCalled();
    await saveBeforeNavigation(
      guard,
      () => Promise.resolve({ ok: true }),
      () => false,
      replay,
    );
    expect(replay).toHaveBeenCalledWith(navigation);
    expect(guard.pending).toBeNull();
  });

  it("keeps the pending dialog when replay fails after saving", async () => {
    const guard = createNavigationGuard();
    const navigation = intent();
    guard.intercept(navigation, dirty);
    await expect(
      saveBeforeNavigation(
        guard,
        () => Promise.resolve({ ok: true }),
        () => false,
        () => Promise.reject(new Error("Navigation failed")),
      ),
    ).rejects.toThrow("Navigation failed");
    expect(guard.pending).toBe(navigation);
  });

  it.each([false, true])(
    "cleans up an aborted replay only while the queue stays clean (new edit: %s)",
    async (newEdit) => {
      const guard = createNavigationGuard();
      const navigation = intent();
      guard.intercept(navigation, dirty);
      let edited = false;
      await expect(
        saveBeforeNavigation(
          guard,
          () => Promise.resolve({ ok: true }),
          () => edited,
          () => {
            edited = newEdit;
            return Promise.reject(new Error("navigation aborted"));
          },
        ),
      ).rejects.toThrow("navigation aborted");
      expect(guard.pending).toBe(newEdit ? navigation : null);
    },
  );

  it("does not resume an obsolete navigation after the dialog was reset", async () => {
    const guard = createNavigationGuard();
    guard.intercept(intent(), dirty);
    const replay = vi.fn().mockResolvedValue(undefined);
    await saveBeforeNavigation(
      guard,
      () => {
        guard.clear();
        guard.intercept(intent({ to: "http://localhost/#/different" }), dirty);
        return Promise.resolve({ ok: true });
      },
      () => false,
      replay,
    );
    expect(replay).not.toHaveBeenCalled();
  });

  it.each([-1, 1, -2])(
    "replays browser history delta %s after restoration without adding an entry",
    async (delta) => {
      const events: string[] = [];
      const actions = {
        restoreHistory: vi.fn(() => {
          events.push("restore");
          return Promise.resolve();
        }),
        historyGo: vi.fn((value: number) => {
          events.push(`go:${value}`);
          return Promise.resolve();
        }),
        goto: vi.fn().mockResolvedValue(undefined),
      };
      await replayNavigation(intent({ type: "popstate", delta }), actions);
      expect(events).toEqual(["restore", `go:${delta}`]);
      expect(actions.goto).not.toHaveBeenCalled();
    },
  );

  it("does not replay history before the cancelled entry is restored", async () => {
    let restore!: () => void;
    const restored = new Promise<void>((resolve) => (restore = resolve));
    const actions = {
      restoreHistory: () => restored,
      historyGo: vi.fn().mockResolvedValue(undefined),
      goto: vi.fn().mockResolvedValue(undefined),
    };
    const replay = replayNavigation(intent({ type: "popstate", delta: -1 }), actions);
    expect(actions.historyGo).not.toHaveBeenCalled();
    restore();
    await replay;
    expect(actions.historyGo).toHaveBeenCalledWith(-1);
  });

  it("replays ordinary links to their original URL", async () => {
    const actions = {
      restoreHistory: vi.fn().mockResolvedValue(undefined),
      historyGo: vi.fn().mockResolvedValue(undefined),
      goto: vi.fn().mockResolvedValue(undefined),
    };
    await replayNavigation(intent(), actions);
    expect(actions.goto).toHaveBeenCalledWith(intent().to);
    expect(actions.historyGo).not.toHaveBeenCalled();
  });
});
