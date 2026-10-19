/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { buildColorByCatalogue, ENTITY_COLOR_MODE } from "../colorByCatalogue";
import { ATTRIBUTE_PALETTE, createRamp, NO_VALUE_COLOR, UNLINKED_COLOR } from "../colorByPalette";
import {
  DEFAULT_COLOR_BY_SETTINGS,
  paletteOf,
  withLearned,
  withSelected,
  withValueColor,
  type AttributePalette,
  type ColorBySettings,
} from "../colorBySettings";
import {
  buildColorResolver,
  createEntityColorOrder,
  ENTITY_MODE,
  resolveActiveMode,
  type ActiveColorMode,
  type ColorAnnotation,
  type ColorEntity,
  type ColorResolver,
  type EntityColorOrder,
} from "../colorResolver";
import { BaseSchema, type FieldInfo } from "$lib/types/dataset";
import { paletteColorAt } from "$lib/utils/coreUtils";
import type { WorkspaceManifest } from "$lib/workspace/manifest";

const field = (type: string): FieldInfo => ({ type, collection: false });

const MANIFEST: Pick<WorkspaceManifest, "tablesByName" | "tablesByGroup"> = {
  tablesByName: {
    entities: {
      name: "entities",
      group: "entities",
      baseSchema: BaseSchema.Entity,
      fields: { category: field("str"), is_difficult: field("bool"), score: field("float") },
    },
    bboxes: {
      name: "bboxes",
      group: "annotations",
      baseSchema: BaseSchema.BBox,
      fields: { annotator: field("str") },
    },
    masks: { name: "masks", group: "annotations", baseSchema: BaseSchema.Mask, fields: {} },
    keypoints: {
      name: "keypoints",
      group: "annotations",
      baseSchema: BaseSchema.Keypoints,
      fields: {},
    },
    text_spans: {
      name: "text_spans",
      group: "annotations",
      baseSchema: BaseSchema.TextSpan,
      fields: { role: field("str") },
    },
    tracklets: {
      name: "tracklets",
      group: "annotations",
      baseSchema: BaseSchema.Tracklet,
      fields: { phase: field("str") },
    },
  },
  tablesByGroup: {
    entities: ["entities"],
    annotations: ["bboxes", "masks", "keypoints", "text_spans", "tracklets"],
    item: [],
    views: [],
    embeddings: [],
  },
};
const CATALOGUE = buildColorByCatalogue(MANIFEST);

const TABLE_BASE: Record<string, BaseSchema> = {
  bboxes: BaseSchema.BBox,
  masks: BaseSchema.Mask,
  keypoints: BaseSchema.Keypoints,
  text_spans: BaseSchema.TextSpan,
  tracklets: BaseSchema.Tracklet,
  messages: BaseSchema.Message,
  not_a_table: BaseSchema.TextSpan,
};

const ent = (id: string, data: Record<string, unknown> = {}, parent = ""): ColorEntity => ({
  id,
  data: { parent_id: parent, ...data },
});

const ann = (
  id: string,
  table: string,
  entityId: string,
  data: Record<string, unknown> = {},
): ColorAnnotation => ({
  id,
  table_info: { name: table, base_schema: TABLE_BASE[table] },
  data: { entity_id: entityId, ...data },
});

// The decoy takes slot 0, whose color equals the unlinked pink: tested objects never use it.
const ENTITIES: ColorEntity[] = [
  ent("decoy", { category: "plane" }),
  ent("car1", { category: "car", is_difficult: true, score: 1 }),
  ent("car2", { category: "truck", is_difficult: false, score: 3 }),
  ent("wheel", { category: "wheel" }, "car1"),
  ent("blank", {}),
  ent("lost", { category: "boat" }, "gone"),
];

function modeOf(selected: string): ActiveColorMode {
  return resolveActiveMode(CATALOGUE, withSelected(DEFAULT_COLOR_BY_SETTINGS, selected));
}

function build(
  selected: string,
  {
    entities = ENTITIES,
    annotations = [],
    palette,
    order = createEntityColorOrder(),
    previous,
  }: {
    entities?: ColorEntity[];
    annotations?: ColorAnnotation[];
    palette?: AttributePalette;
    order?: EntityColorOrder;
    previous?: ColorResolver;
  } = {},
): ColorResolver {
  return buildColorResolver(
    { mode: modeOf(selected), palette, entities, annotations, entityOrder: order },
    previous,
  );
}

/** Apply what a build asks to remember, as the store does. */
function remember(settings: ColorBySettings, resolver: ColorResolver): ColorBySettings {
  const pending = resolver.pendingLearned;
  return pending ? withLearned(settings, pending.attributeId, pending) : settings;
}

const HEX = /^#[0-9a-f]{6}$/;

describe("resolveActiveMode", () => {
  it("selects Entity, a known attribute, or Entity for an attribute the schema lacks", () => {
    expect(modeOf(ENTITY_COLOR_MODE)).toBe(ENTITY_MODE);
    expect(modeOf("entities.category")).toMatchObject({
      kind: "attribute",
      attribute: { id: "entities.category" },
    });
    expect(modeOf("entities.gone")).toBe(ENTITY_MODE);
  });
});

describe("Entity mode", () => {
  it("gives top-level objects palette colors in first-seen order", () => {
    const resolver = build(ENTITY_COLOR_MODE);

    expect(resolver.colorOfEntity("decoy")).toBe(paletteColorAt(0));
    expect(resolver.colorOfEntity("car1")).toBe(paletteColorAt(1));
    expect(resolver.colorOfEntity("car2")).toBe(paletteColorAt(2));
    expect(resolver.legend).toBeNull();
    expect(resolver.pendingLearned).toBeNull();
  });

  it("colors unknown, empty and orphan ids as unlinked", () => {
    const resolver = build(ENTITY_COLOR_MODE);

    expect(resolver.colorOfEntity("nobody")).toBe(UNLINKED_COLOR);
    expect(resolver.colorOfEntity("")).toBe(UNLINKED_COLOR);
    expect(resolver.colorOfEntity("lost")).toBe(UNLINKED_COLOR);
  });

  it("keeps slots across records, including for objects no longer present", () => {
    const order = createEntityColorOrder();
    build(ENTITY_COLOR_MODE, { order });
    const next = build(ENTITY_COLOR_MODE, {
      order,
      entities: [ent("newcomer"), ent("car2", { category: "truck" })],
    });

    expect(next.colorOfEntity("car2")).toBe(paletteColorAt(2));
    expect(next.colorOfEntity("newcomer")).toBe(
      paletteColorAt(ENTITIES.filter((e) => e.data.parent_id === "").length),
    );
  });

  it("keeps the slots allocated while an attribute was selected", () => {
    const order = createEntityColorOrder();
    build("entities.category", { order, entities: [ent("x"), ent("y")] });
    const back = build(ENTITY_COLOR_MODE, { order, entities: [ent("y"), ent("x")] });

    expect(back.colorOfEntity("x")).toBe(paletteColorAt(0));
    expect(back.colorOfEntity("y")).toBe(paletteColorAt(1));
  });

  // Regressions: these surfaces resolved a sub-entity's own id, absent from the scale, to pink.
  it("colors the shapes, spans and tracks of a sub-entity like its object", () => {
    const resolver = build(ENTITY_COLOR_MODE);
    const carColor = resolver.colorOfEntity("car1");

    expect(carColor).not.toBe(UNLINKED_COLOR);
    expect(resolver.colorOfEntity("wheel")).toBe(carColor);
    expect(resolver.colorOfAnnotation({ id: "m1", data: { entity_id: "wheel" } })).toBe(carColor);
    expect(resolver.colorOfAnnotation({ id: "k1", entityRef: { id: "wheel" } })).toBe(carColor);
    expect(resolver.colorOfAnnotation(ann("s1", "text_spans", "wheel"))).toBe(carColor);
    expect(resolver.colorOfAnnotation(ann("t1", "tracklets", "wheel"))).toBe(carColor);
  });

  it("colors an annotation like its object, not by its own id", () => {
    const resolver = build(ENTITY_COLOR_MODE);

    expect(resolver.colorOfAnnotation(ann("b1", "bboxes", "car2"))).toBe(
      resolver.colorOfEntity("car2"),
    );
  });

  it("colors drafts and previews as unlinked", () => {
    const resolver = build(ENTITY_COLOR_MODE);

    expect(resolver.colorOfAnnotation({ id: "preview", data: { entity_id: "" } })).toBe(
      UNLINKED_COLOR,
    );
    expect(resolver.colorOfAnnotation({ id: "draft" })).toBe(UNLINKED_COLOR);
  });
});

describe("entity attributes", () => {
  it("colors every shape of an object by its value, sub-entities included", () => {
    const resolver = build("entities.category");
    const car = resolver.colorOfEntity("car1");

    expect(ATTRIBUTE_PALETTE).toContain(car);
    expect(resolver.colorOfEntity("wheel")).toBe(car);
    expect(resolver.colorOfAnnotation(ann("b1", "bboxes", "wheel"))).toBe(car);
    expect(resolver.colorOfEntity("car2")).not.toBe(car);
    expect(resolver.colorOfEntity("blank")).toBe(NO_VALUE_COLOR);
  });

  it("colors an orphan sub-entity by its own value", () => {
    const resolver = build("entities.category");

    expect(resolver.colorOfEntity("lost")).not.toBe(UNLINKED_COLOR);
    expect(resolver.colorOfEntity("lost")).not.toBe(NO_VALUE_COLOR);
  });

  it("describes the record's values in the legend", () => {
    const legend = build("entities.category").legend;

    expect(legend).toMatchObject({
      kind: "categorical",
      unit: "objects",
      noValueCount: 1,
      otherCount: 0,
    });
    if (legend?.kind !== "categorical") throw new Error("categorical legend expected");
    expect(legend.entries.map((entry) => [entry.key, entry.count])).toEqual([
      ["boat", 1],
      ["car", 1],
      ["plane", 1],
      ["truck", 1],
    ]);
    expect(legend.itemCount).toBe(4);
    expect(legend.sharedColorCount).toBe(0);
    expect(legend.customized).toBe(false);
  });

  it("asks to remember the order of new values, and stops once remembered", () => {
    let settings = withSelected(DEFAULT_COLOR_BY_SETTINGS, "entities.category");
    const first = build("entities.category", { palette: paletteOf(settings, "entities.category") });

    expect(first.pendingLearned).toEqual({
      attributeId: "entities.category",
      order: ["boat", "car", "plane", "truck"],
    });
    settings = remember(settings, first);
    const second = build("entities.category", {
      palette: paletteOf(settings, "entities.category"),
    });
    expect(second.pendingLearned).toBeNull();
  });

  it("keeps a value's color from one record to the next", () => {
    let settings = withSelected(DEFAULT_COLOR_BY_SETTINGS, "entities.category");
    const first = build("entities.category", {
      entities: [ent("decoy", { category: "plane" }), ent("a", { category: "truck" })],
      palette: paletteOf(settings, "entities.category"),
    });
    settings = remember(settings, first);
    const second = build("entities.category", {
      entities: [ent("b", { category: "bus" }), ent("c", { category: "truck" })],
      palette: paletteOf(settings, "entities.category"),
    });

    expect(second.colorOfEntity("c")).toBe(first.colorOfEntity("a"));
    expect(second.colorOfEntity("b")).not.toBe(second.colorOfEntity("c"));
    expect(second.pendingLearned?.order).toEqual(["plane", "truck", "bus"]);
  });

  it("follows an edited value once rebuilt", () => {
    const entities = [ent("decoy", { category: "plane" }), ent("a", { category: "car" })];
    const before = build("entities.category", { entities });
    const edited = { ...entities[1], data: { ...entities[1].data, category: "plane" } };
    const after = build("entities.category", { entities: [entities[0], edited], previous: before });

    expect(after).not.toBe(before);
    expect(after.colorOfEntity("a")).toBe(after.colorOfEntity("decoy"));
  });

  it("lists remembered values the record lacks", () => {
    const legend = build("entities.category", {
      entities: [ent("a", { category: "car" })],
      palette: { order: ["truck", "car", "bus"] },
    }).legend;

    if (legend?.kind !== "categorical") throw new Error("categorical legend expected");
    expect(legend.entries.map((entry) => entry.key)).toEqual(["car"]);
    expect(legend.knownEntries.map((entry) => [entry.key, entry.count])).toEqual([
      ["bus", 0],
      ["truck", 0],
    ]);
  });

  it("prefers the user's colors and reports values that share one", () => {
    const base = withSelected(DEFAULT_COLOR_BY_SETTINGS, "entities.category");
    const learned = remember(base, build("entities.category", { palette: undefined }));
    const truckColor = build("entities.category", {
      palette: paletteOf(learned, "entities.category"),
    }).colorOfEntity("car2");
    const custom = withValueColor(learned, "entities.category", "car", truckColor);
    const resolver = build("entities.category", {
      palette: paletteOf(custom, "entities.category"),
    });
    const legend = resolver.legend;

    expect(resolver.colorOfEntity("car1")).toBe(truckColor);
    if (legend?.kind !== "categorical") throw new Error("categorical legend expected");
    expect(legend.customized).toBe(true);
    expect(legend.entries.find((entry) => entry.key === "car")?.custom).toBe(true);
    expect(legend.sharedColorCount).toBe(2);
  });

  it("gives false and true their own colors even when one is missing", () => {
    const resolver = build("entities.is_difficult");

    expect(resolver.colorOfEntity("car2")).toBe(ATTRIBUTE_PALETTE[0]);
    expect(resolver.colorOfEntity("car1")).toBe(ATTRIBUTE_PALETTE[1]);
    expect(resolver.colorOfEntity("decoy")).toBe(NO_VALUE_COLOR);

    const onlyTrue = build("entities.is_difficult", {
      entities: [ent("x", { is_difficult: true })],
    });
    expect(onlyTrue.colorOfEntity("x")).toBe(ATTRIBUTE_PALETTE[1]);
  });

  it("ramps numbers over the range seen, which only widens", () => {
    let settings = withSelected(DEFAULT_COLOR_BY_SETTINGS, "entities.score");
    const ramp = createRamp();
    const first = build("entities.score", { palette: paletteOf(settings, "entities.score") });

    expect(first.colorOfEntity("car1")).toBe(ramp.low);
    expect(first.colorOfEntity("car2")).toBe(ramp.high);
    expect(first.colorOfEntity("decoy")).toBe(NO_VALUE_COLOR);
    expect(first.pendingLearned).toEqual({
      attributeId: "entities.score",
      seen: { min: 1, max: 3 },
    });

    settings = remember(settings, first);
    const inside = build("entities.score", {
      entities: [ent("x", { score: 3 })],
      palette: paletteOf(settings, "entities.score"),
    });
    expect(inside.colorOfEntity("x")).toBe(ramp.high);
    expect(inside.pendingLearned).toBeNull();

    const wider = build("entities.score", {
      entities: [ent("x", { score: 5 })],
      palette: paletteOf(settings, "entities.score"),
    });
    expect(wider.pendingLearned?.seen).toEqual({ min: 1, max: 5 });
  });

  it("puts a single value in the middle of the ramp", () => {
    const resolver = build("entities.score", { entities: [ent("x", { score: 2 })] });

    expect(resolver.colorOfEntity("x")).toBe(createRamp().colorAt(0.5));
  });

  it("ignores remembered parts that do not fit the attribute's current type", () => {
    const numeric = build("entities.score", {
      palette: { order: ["1", "3"], colors: { "1": "#123456" } },
    });
    expect(numeric.colorOfEntity("car1")).toBe(createRamp().low);

    const categorical = build("entities.category", { palette: { seen: { min: 0, max: 1 } } });
    expect(ATTRIBUTE_PALETTE).toContain(categorical.colorOfEntity("car1"));
  });
});

describe("annotation attributes", () => {
  const ANNOTATIONS: ColorAnnotation[] = [
    ann("b1", "bboxes", "car1", { annotator: "alice", tracklet_id: "t1" }),
    ann("b2", "bboxes", "car1", { annotator: "alice", tracklet_id: "t1" }),
    ann("b3", "bboxes", "wheel", { annotator: "bob", tracklet_id: "t1" }),
    ann("b4", "bboxes", "car2", { annotator: "", confidence: -1 }),
    ann("b5", "bboxes", "car2", { annotator: "bob", confidence: 0 }),
    ann("b6", "bboxes", "car2", { annotator: "bob", confidence: 1 }),
    ann("m1", "masks", "car1"),
    ann("k1", "keypoints", "car2", { tracklet_id: "t2" }),
    ann("t1", "tracklets", "car1", { phase: "moving" }),
    ann("t2", "tracklets", "car2", { phase: "parked" }),
    ann("t3", "tracklets", "decoy"),
  ];

  it("colors the rows of the attribute's table by their own value, others as no value", () => {
    const resolver = build("bboxes.annotator", { annotations: ANNOTATIONS });
    const alice = resolver.colorOfAnnotation(ANNOTATIONS[0]);

    expect(ATTRIBUTE_PALETTE).toContain(alice);
    expect(resolver.colorOfAnnotation(ANNOTATIONS[2])).not.toBe(alice);
    expect(resolver.colorOfAnnotation(ANNOTATIONS[3])).toBe(NO_VALUE_COLOR);
    expect(resolver.colorOfAnnotation(ann("m1", "masks", "car1"))).toBe(NO_VALUE_COLOR);
    expect(resolver.legend).toMatchObject({
      unit: "annotations",
      itemCount: 5,
      noValueCount: 1,
      otherCount: 2,
    });
  });

  it("resolves ghosts, keypoint shapes and stale copies by their stored row", () => {
    const resolver = build("bboxes.annotator", { annotations: ANNOTATIONS });
    const bob = resolver.colorOfAnnotation(ANNOTATIONS[2]);

    const ghost = {
      id: "b3::7",
      data: { entity_id: "wheel", annotator: "stale" },
      ui: { startRef: { id: "b3" } },
    };
    expect(resolver.colorOfAnnotation(ghost)).toBe(bob);
    expect(resolver.colorOfAnnotation({ id: "k1", entityRef: { id: "car2" } })).toBe(
      NO_VALUE_COLOR,
    );
    const staleCopy = { id: "b1", data: { entity_id: "car1", annotator: "bob" } };
    expect(resolver.colorOfAnnotation(staleCopy)).toBe(resolver.colorOfAnnotation(ANNOTATIONS[0]));
  });

  it("shows the most frequent value on objects and tracks", () => {
    const resolver = build("bboxes.annotator", { annotations: ANNOTATIONS });
    const alice = resolver.colorOfAnnotation(ANNOTATIONS[0]);
    const bob = resolver.colorOfAnnotation(ANNOTATIONS[2]);

    expect(resolver.colorOfEntity("car1")).toBe(alice);
    expect(resolver.colorOfEntity("wheel")).toBe(alice);
    expect(resolver.colorOfEntity("car2")).toBe(bob);
    expect(resolver.colorOfEntity("decoy")).toBe(NO_VALUE_COLOR);
    expect(resolver.colorOfAnnotation(ANNOTATIONS[8])).toBe(alice);
    expect(resolver.colorOfAnnotation(ANNOTATIONS[10])).toBe(NO_VALUE_COLOR);
  });

  it("breaks a tie toward the value with the earlier color", () => {
    const resolver = build("bboxes.annotator", {
      annotations: [
        ann("x1", "bboxes", "car1", { annotator: "zoe" }),
        ann("x2", "bboxes", "car1", { annotator: "adam" }),
      ],
      palette: { order: ["zoe", "adam"] },
    });

    expect(resolver.colorOfEntity("car1")).toBe(ATTRIBUTE_PALETTE[0]);
  });

  it("averages numbers on objects", () => {
    const resolver = build("bboxes.confidence", {
      annotations: [
        ann("x1", "bboxes", "car1", { confidence: 0 }),
        ann("x2", "bboxes", "car1", { confidence: 1 }),
        ann("x3", "bboxes", "car1", { confidence: -1 }),
      ],
    });

    expect(resolver.colorOfEntity("car1")).toBe(createRamp().colorAt(0.5));
  });

  it("ramps the box confidence on its fixed range, -1 being no value", () => {
    const resolver = build("bboxes.confidence", { annotations: ANNOTATIONS });
    const ramp = createRamp();

    expect(resolver.colorOfAnnotation(ANNOTATIONS[3])).toBe(NO_VALUE_COLOR);
    expect(resolver.colorOfAnnotation(ANNOTATIONS[4])).toBe(ramp.low);
    expect(resolver.colorOfAnnotation(ANNOTATIONS[5])).toBe(ramp.high);
    expect(resolver.legend).toMatchObject({
      kind: "numeric",
      domain: { min: 0, max: 1, source: "fixed" },
    });
    expect(resolver.pendingLearned).toBeNull();
  });

  it("gives shapes their track's value when the attribute is on tracks", () => {
    const resolver = build("tracklets.phase", { annotations: ANNOTATIONS });
    const moving = resolver.colorOfAnnotation(ANNOTATIONS[8]);

    expect(resolver.colorOfAnnotation(ANNOTATIONS[0])).toBe(moving);
    expect(resolver.colorOfAnnotation(ANNOTATIONS[2])).toBe(moving);
    expect(resolver.colorOfAnnotation(ANNOTATIONS[7])).toBe(
      resolver.colorOfAnnotation(ANNOTATIONS[9]),
    );
    expect(resolver.colorOfAnnotation(ANNOTATIONS[6])).toBe(NO_VALUE_COLOR);
    expect(resolver.legend).toMatchObject({ unit: "tracks", itemCount: 2, noValueCount: 1 });
  });

  it("leaves drafts, previews, chat messages and duplicates out", () => {
    const temporarySpan = ann("tmp", "not_a_table", "");
    const resolver = build("text_spans.role", {
      annotations: [
        ann("s1", "text_spans", "car1", { role: "agent" }),
        ann("s1", "text_spans", "car1", { role: "agent" }),
        ann("msg", "messages", "car1", { role: "agent" }),
        temporarySpan,
      ],
    });

    expect(resolver.colorOfAnnotation(temporarySpan)).toBe(UNLINKED_COLOR);
    expect(resolver.legend).toMatchObject({ itemCount: 1, otherCount: 0 });
    expect(build(ENTITY_COLOR_MODE).colorOfAnnotation(temporarySpan)).toBe(UNLINKED_COLOR);
  });
});

describe("reuse", () => {
  it("returns the previous resolver when no color changed", () => {
    const annotations = [ann("b1", "bboxes", "car1", { annotator: "alice" })];
    const first = build("bboxes.annotator", { annotations });
    const again = build("bboxes.annotator", {
      annotations: [{ ...annotations[0], data: { ...annotations[0].data } }],
      previous: first,
    });

    expect(again).toBe(first);
  });

  it("returns a new resolver when a color, an object or the mode changes", () => {
    const order = createEntityColorOrder();
    const first = build(ENTITY_COLOR_MODE, { order });

    expect(build(ENTITY_COLOR_MODE, { order, previous: first })).toBe(first);
    expect(
      build(ENTITY_COLOR_MODE, {
        order,
        entities: [...ENTITIES, ent("bolt", {}, "car2")],
        previous: first,
      }),
    ).not.toBe(first);
    expect(build("entities.category", { order, previous: first })).not.toBe(first);
  });
});

describe("every mode", () => {
  it("only returns #rrggbb colors", () => {
    const annotations = [
      ann("b1", "bboxes", "car1", { annotator: "alice", confidence: 0.3 }),
      ann("t1", "tracklets", "car1", { phase: "moving" }),
      ann("s1", "text_spans", "wheel", { role: "agent" }),
    ];
    const ids = ["decoy", "car1", "car2", "wheel", "blank", "lost", "nobody", ""];
    for (const option of [ENTITY_COLOR_MODE, ...CATALOGUE.attributes.map((a) => a.id)]) {
      const resolver = build(option, { annotations });
      for (const id of ids) expect(resolver.colorOfEntity(id)).toMatch(HEX);
      for (const row of annotations) expect(resolver.colorOfAnnotation(row)).toMatch(HEX);
    }
  });
});
