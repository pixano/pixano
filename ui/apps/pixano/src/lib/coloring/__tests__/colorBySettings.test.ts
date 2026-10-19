/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { afterEach, describe, expect, it, vi } from "vitest";

import { MAX_LEARNED_VALUES, MAX_VALUE_KEY_LENGTH } from "../colorByPalette";
import {
  browserStorage,
  colorByStorageKey,
  decodeColorBySettings,
  DEFAULT_COLOR_BY_SETTINGS,
  encodeColorBySettings,
  hasCustomColors,
  isDefaultColorBySettings,
  MAX_CUSTOM_COLORS,
  MAX_PALETTES,
  paletteOf,
  readStoredColorBySettings,
  withLearned,
  withoutCustomColors,
  withoutLearned,
  withoutSeenRange,
  withRampColor,
  withSelected,
  withValueColor,
  writeStoredColorBySettings,
  type ColorBySettings,
  type KeyValueStorage,
} from "../colorBySettings";

function memoryStorage(): KeyValueStorage & { data: Map<string, string> } {
  const data = new Map<string, string>();
  return {
    data,
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => void data.set(key, value),
    removeItem: (key) => void data.delete(key),
  };
}

const stored = (value: unknown) => JSON.stringify(value);

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("decodeColorBySettings", () => {
  it("falls back to the defaults on missing, malformed or foreign data", () => {
    expect(decodeColorBySettings(null)).toBe(DEFAULT_COLOR_BY_SETTINGS);
    expect(decodeColorBySettings("{not json")).toBe(DEFAULT_COLOR_BY_SETTINGS);
    expect(decodeColorBySettings("[]")).toBe(DEFAULT_COLOR_BY_SETTINGS);
    expect(decodeColorBySettings('"entity"')).toBe(DEFAULT_COLOR_BY_SETTINGS);
    expect(decodeColorBySettings(stored({ v: 2, selected: "entities.category" }))).toBe(
      DEFAULT_COLOR_BY_SETTINGS,
    );
  });

  it("keeps a selection it does not know: the schema decides later", () => {
    expect(decodeColorBySettings(stored({ v: 1, selected: "entities.gone" })).selected).toBe(
      "entities.gone",
    );
    expect(decodeColorBySettings(stored({ v: 1, selected: 3 })).selected).toBe("entity");
    expect(decodeColorBySettings(stored({ v: 1, selected: "" })).selected).toBe("entity");
  });

  it("drops each invalid part on its own", () => {
    const settings = decodeColorBySettings(
      stored({
        v: 1,
        selected: "entities.category",
        palettes: {
          "entities.category": {
            order: ["car", 3, "car", "truck", "x".repeat(MAX_VALUE_KEY_LENGTH + 1)],
            colors: { car: "#FF0000", truck: "red", bus: "#12345" },
            ramp: { low: "#00ff00", high: "nope" },
            seen: { min: 5, max: 1 },
          },
          "entities.score": { seen: { min: 0, max: Number.MAX_VALUE } },
          "entities.empty": { order: [], colors: {} },
          "entities.bad": "not a palette",
        },
      }),
    );

    expect(paletteOf(settings, "entities.category")).toEqual({
      order: ["car", "truck"],
      colors: { car: "#ff0000" },
      ramp: { low: "#00ff00" },
    });
    expect(paletteOf(settings, "entities.score")).toEqual({
      seen: { min: 0, max: Number.MAX_VALUE },
    });
    expect(paletteOf(settings, "entities.empty")).toBeUndefined();
    expect(paletteOf(settings, "entities.bad")).toBeUndefined();
  });

  it("caps what it reads", () => {
    const palettes = Object.fromEntries(
      Array.from({ length: MAX_PALETTES + 5 }, (_, i) => [`t.f${i}`, { order: ["a"] }]),
    );
    const colors = Object.fromEntries(
      Array.from({ length: MAX_CUSTOM_COLORS + 5 }, (_, i) => [`v${i}`, "#000000"]),
    );
    const order = Array.from({ length: MAX_LEARNED_VALUES + 5 }, (_, i) => `v${i}`);
    const settings = decodeColorBySettings(
      stored({ v: 1, selected: "entity", palettes: { ...palettes, "t.big": { order, colors } } }),
    );

    expect(Object.keys(settings.palettes)).toHaveLength(MAX_PALETTES);
    const big = decodeColorBySettings(
      stored({ v: 1, selected: "entity", palettes: { "t.big": { order, colors } } }),
    ).palettes["t.big"];
    expect(big.order).toHaveLength(MAX_LEARNED_VALUES);
    expect(Object.keys(big.colors ?? {})).toHaveLength(MAX_CUSTOM_COLORS);
  });

  it("keeps values named like object properties as plain keys", () => {
    const settings = decodeColorBySettings(
      '{"v":1,"selected":"t.f","palettes":{"t.f":{"order":["__proto__","constructor"],' +
        '"colors":{"__proto__":"#010203","constructor":"#040506"}}}}',
    );
    const palette = paletteOf(settings, "t.f");

    expect(palette?.order).toEqual(["__proto__", "constructor"]);
    expect(Object.hasOwn(palette?.colors ?? {}, "__proto__")).toBe(true);
    expect(palette?.colors?.["constructor"]).toBe("#040506");
    expect(Object.getPrototypeOf(palette?.colors)).toBe(Object.prototype);
    expect(paletteOf(settings, "constructor")).toBeUndefined();
    expect(paletteOf(settings, "__proto__")).toBeUndefined();
  });

  it("round-trips through the encoder", () => {
    const settings: ColorBySettings = {
      selected: "bboxes.confidence",
      palettes: {
        "bboxes.confidence": { ramp: { low: "#000000", high: "#ffffff" } },
        "entities.category": {
          order: ["a", "b"],
          colors: { b: "#123456" },
          seen: { min: 1, max: 2 },
        },
      },
    };

    expect(decodeColorBySettings(encodeColorBySettings(settings))).toEqual(settings);
  });
});

describe("updaters", () => {
  const base: ColorBySettings = {
    selected: "entities.category",
    palettes: { "entities.category": { order: ["car", "truck"], seen: { min: 0, max: 1 } } },
  };

  it("select an option, and return the same settings when nothing changes", () => {
    expect(withSelected(base, "entity").selected).toBe("entity");
    expect(withSelected(base, "entities.category")).toBe(base);
    expect(withSelected(base, "")).toBe(base);
  });

  it("set a value's color, normalized, and ignore invalid or unchanged colors", () => {
    const next = withValueColor(base, "entities.category", "car", "#FF0000");

    expect(paletteOf(next, "entities.category")?.colors).toEqual({ car: "#ff0000" });
    expect(paletteOf(next, "entities.category")?.order).toEqual(["car", "truck"]);
    expect(withValueColor(next, "entities.category", "car", "red")).toBe(next);
    expect(withValueColor(base, "entities.category", "car", "nope")).toBe(base);
  });

  it("set a color for a value named like an object property", () => {
    const next = withValueColor(base, "entities.category", "__proto__", "#010203");

    expect(Object.hasOwn(paletteOf(next, "entities.category")?.colors ?? {}, "__proto__")).toBe(
      true,
    );
  });

  it("refuse a color beyond the cap of custom colors", () => {
    let settings: ColorBySettings = DEFAULT_COLOR_BY_SETTINGS;
    for (let i = 0; i < MAX_CUSTOM_COLORS; i++) {
      settings = withValueColor(settings, "t.f", `v${i}`, "#000000");
    }

    expect(withValueColor(settings, "t.f", "one more", "#000000")).toBe(settings);
    expect(withValueColor(settings, "t.f", "v0", "#ffffff")).not.toBe(settings);
  });

  it("set a ramp end color", () => {
    const next = withRampColor(base, "bboxes.confidence", "high", "#00FF00");

    expect(paletteOf(next, "bboxes.confidence")).toEqual({ ramp: { high: "#00ff00" } });
    expect(withRampColor(next, "bboxes.confidence", "high", "#00ff00")).toBe(next);
  });

  it("remember a longer order or a wider range only", () => {
    expect(withLearned(base, "entities.category", { order: ["car"] })).toBe(base);
    expect(withLearned(base, "entities.category", { seen: { min: 0.2, max: 0.8 } })).toBe(base);

    const longer = withLearned(base, "entities.category", { order: ["car", "truck", "bus"] });
    expect(paletteOf(longer, "entities.category")?.order).toEqual(["car", "truck", "bus"]);

    const wider = withLearned(base, "entities.category", { seen: { min: -1, max: 1 } });
    expect(paletteOf(wider, "entities.category")?.seen).toEqual({ min: -1, max: 1 });
  });

  it("reset custom colors but keep the order and the range", () => {
    const custom = withRampColor(
      withValueColor(base, "entities.category", "car", "#123456"),
      "entities.category",
      "low",
      "#000000",
    );
    const reset = withoutCustomColors(custom, "entities.category");

    expect(paletteOf(reset, "entities.category")).toEqual({
      order: ["car", "truck"],
      seen: { min: 0, max: 1 },
    });
    expect(withoutCustomColors(reset, "entities.category")).toBe(reset);
    expect(hasCustomColors(paletteOf(custom, "entities.category"))).toBe(true);
    expect(hasCustomColors(paletteOf(reset, "entities.category"))).toBe(false);
  });

  it("forget the range seen", () => {
    const next = withoutSeenRange(base, "entities.category");

    expect(paletteOf(next, "entities.category")).toEqual({ order: ["car", "truck"] });
    expect(withoutSeenRange(next, "entities.category")).toBe(next);
  });

  it("drop what was learned, keeping the user's colors", () => {
    const custom = withValueColor(base, "entities.category", "car", "#123456");

    expect(withoutLearned(custom).palettes).toEqual({
      "entities.category": { colors: { car: "#123456" } },
    });
  });

  it("forget the oldest palettes past the cap, never the selected one", () => {
    let settings: ColorBySettings = { selected: "t.first", palettes: {} };
    for (let i = 0; i <= MAX_PALETTES; i++) {
      const id = i === 0 ? "t.first" : `t.f${i}`;
      settings = withLearned(settings, id, { order: ["a"] });
    }

    expect(Object.keys(settings.palettes)).toHaveLength(MAX_PALETTES);
    expect(paletteOf(settings, "t.first")).toBeDefined();
    expect(paletteOf(settings, "t.f1")).toBeUndefined();
  });
});

describe("storage", () => {
  it("keys settings by dataset", () => {
    expect(colorByStorageKey("ds-1")).toBe("pixano.workspace.colorBy.ds-1");
  });

  it("writes, reads back, and keeps datasets apart", () => {
    const storage = memoryStorage();
    const settings = withSelected(DEFAULT_COLOR_BY_SETTINGS, "entities.category");

    expect(writeStoredColorBySettings(storage, "a", settings)).toBe(true);
    expect(readStoredColorBySettings(storage, "a")).toEqual(settings);
    expect(readStoredColorBySettings(storage, "b")).toBeNull();
  });

  it("removes the key when the settings are back to the defaults", () => {
    const storage = memoryStorage();
    writeStoredColorBySettings(storage, "a", withSelected(DEFAULT_COLOR_BY_SETTINGS, "t.f"));
    writeStoredColorBySettings(storage, "a", DEFAULT_COLOR_BY_SETTINGS);

    expect(storage.data.has(colorByStorageKey("a"))).toBe(false);
    expect(isDefaultColorBySettings(DEFAULT_COLOR_BY_SETTINGS)).toBe(true);
  });

  it("stores the settings without what was learned when space runs out", () => {
    const storage = memoryStorage();
    const setItem = vi.fn((key: string, value: string) => {
      if (value.includes('"order"')) throw new DOMException("full", "QuotaExceededError");
      storage.data.set(key, value);
    });
    const settings = withValueColor(
      withLearned(withSelected(DEFAULT_COLOR_BY_SETTINGS, "t.f"), "t.f", { order: ["a", "b"] }),
      "t.f",
      "a",
      "#123456",
    );

    expect(writeStoredColorBySettings({ ...storage, setItem }, "a", settings)).toBe(true);
    expect(paletteOf(readStoredColorBySettings(storage, "a"), "t.f")).toEqual({
      colors: { a: "#123456" },
    });
  });

  it("survives a storage that throws, or none at all", () => {
    const throwing: KeyValueStorage = {
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

    expect(readStoredColorBySettings(throwing, "a")).toBeNull();
    expect(writeStoredColorBySettings(throwing, "a", DEFAULT_COLOR_BY_SETTINGS)).toBe(false);
    expect(readStoredColorBySettings(null, "a")).toBeNull();
    expect(writeStoredColorBySettings(null, "a", DEFAULT_COLOR_BY_SETTINGS)).toBe(false);
  });

  it("reads the browser's storage through window only", () => {
    vi.stubGlobal("window", undefined);
    expect(browserStorage()).toBeNull();

    const storage = memoryStorage();
    vi.stubGlobal("window", { localStorage: storage });
    expect(browserStorage()).toBe(storage);

    vi.stubGlobal("window", {
      get localStorage() {
        throw new Error("SecurityError");
      },
    });
    expect(browserStorage()).toBeNull();
  });
});
