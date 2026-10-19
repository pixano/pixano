/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it, vi } from "vitest";

import { EMPTY_COLOR_BY_CATALOGUE, type ColorByCatalogue } from "../colorByCatalogue";
import { createColorBySession } from "../colorBySession";
import {
  colorByStorageKey,
  DEFAULT_COLOR_BY_SETTINGS,
  encodeColorBySettings,
  withSelected,
  type KeyValueStorage,
} from "../colorBySettings";

function memoryStorage(): KeyValueStorage & { data: Map<string, string> } {
  const data = new Map<string, string>();
  return {
    data,
    getItem: vi.fn((key: string) => data.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => void data.set(key, value)),
    removeItem: vi.fn((key: string) => void data.delete(key)),
  };
}

function catalogue(signature: string): ColorByCatalogue {
  return { attributes: [], byId: new Map(), signature };
}

const select = (selected: string) => (settings: typeof DEFAULT_COLOR_BY_SETTINGS) =>
  withSelected(settings, selected);

describe("createColorBySession", () => {
  it("reads a dataset's stored settings when it is bound", () => {
    const storage = memoryStorage();
    storage.data.set(
      colorByStorageKey("a"),
      encodeColorBySettings(withSelected(DEFAULT_COLOR_BY_SETTINGS, "entities.category")),
    );
    const session = createColorBySession(() => storage);

    expect(session.configure("a", catalogue("x"))).toBe(true);
    expect(session.datasetId).toBe("a");
    expect(session.settings.selected).toBe("entities.category");
    expect(session.catalogue.signature).toBe("x");
  });

  it("reads storage again only when the dataset changes", () => {
    const storage = memoryStorage();
    const session = createColorBySession(() => storage);

    session.configure("a", catalogue("x"));
    session.configure("a", catalogue("x"));
    expect(storage.getItem).toHaveBeenCalledTimes(1);

    storage.data.set(
      colorByStorageKey("b"),
      encodeColorBySettings(withSelected(DEFAULT_COLOR_BY_SETTINGS, "t.f")),
    );
    expect(session.configure("b", catalogue("x"))).toBe(true);
    expect(session.settings.selected).toBe("t.f");
    expect(storage.getItem).toHaveBeenCalledTimes(2);
  });

  it("keeps the catalogue it has when the schema is the same", () => {
    const session = createColorBySession(() => null);
    const first = catalogue("x");

    session.configure("a", first);
    expect(session.configure("a", catalogue("x"))).toBe(false);
    expect(session.catalogue).toBe(first);
    expect(session.configure("a", catalogue("y"))).toBe(true);
    expect(session.catalogue.signature).toBe("y");
  });

  it("stores each change for the bound dataset", () => {
    const storage = memoryStorage();
    const session = createColorBySession(() => storage);
    session.configure("a", catalogue("x"));

    expect(session.apply(select("entities.category"))).toBe(true);
    expect(storage.data.get(colorByStorageKey("a"))).toContain("entities.category");
    expect(session.apply(select("entities.category"))).toBe(false);
  });

  it("writes nothing while no dataset is bound", () => {
    const storage = memoryStorage();
    const session = createColorBySession(() => storage);

    expect(session.apply(select("entities.category"))).toBe(true);
    expect(storage.setItem).not.toHaveBeenCalled();
  });

  it("reads storage again after a reset", () => {
    const storage = memoryStorage();
    const session = createColorBySession(() => storage);
    session.configure("a", catalogue("x"));
    session.apply(select("t.f"));

    session.reset();
    expect(session.datasetId).toBeNull();
    expect(session.settings).toBe(DEFAULT_COLOR_BY_SETTINGS);
    expect(session.catalogue).toBe(EMPTY_COLOR_BY_CATALOGUE);

    session.configure("a", catalogue("x"));
    expect(session.settings.selected).toBe("t.f");
    expect(storage.getItem).toHaveBeenCalledTimes(2);
  });

  it("keeps a stored selection the schema lacks until the user changes it", () => {
    const storage = memoryStorage();
    const raw = encodeColorBySettings(withSelected(DEFAULT_COLOR_BY_SETTINGS, "entities.gone"));
    storage.data.set(colorByStorageKey("a"), raw);
    const session = createColorBySession(() => storage);

    session.configure("a", catalogue("x"));
    expect(session.settings.selected).toBe("entities.gone");
    expect(storage.data.get(colorByStorageKey("a"))).toBe(raw);
  });

  it("keeps settings in memory when storage is missing", () => {
    const session = createColorBySession(() => null);
    session.configure("a", catalogue("x"));
    session.apply(select("t.f"));

    session.reset();
    session.configure("a", catalogue("x"));
    expect(session.settings.selected).toBe("t.f");

    session.configure("b", catalogue("x"));
    expect(session.settings).toBe(DEFAULT_COLOR_BY_SETTINGS);
  });

  it("keeps settings in memory when storage fails", () => {
    const failing: KeyValueStorage = {
      getItem: () => {
        throw new Error("denied");
      },
      setItem: () => {
        throw new Error("denied");
      },
      removeItem: () => {
        throw new Error("denied");
      },
    };
    const session = createColorBySession(() => failing);
    session.configure("a", catalogue("x"));

    expect(session.apply(select("t.f"))).toBe(true);
    session.reset();
    session.configure("a", catalogue("x"));
    expect(session.settings.selected).toBe("t.f");
  });
});
