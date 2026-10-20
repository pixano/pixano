/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  cornerLabel,
  extendTimelineRanks,
  fusionHighlightState,
  isHiddenInInspector,
  orderTimelineRows,
  rankTimelineRows,
  resolveSelectedRow,
  rowGraphicsOpacity,
  rowKeyframeLabel,
  sameTimelineRowList,
  storedSelfEntityId,
  TIMELINE_EMPTY_TEXT,
  timelineEmptyState,
  togglePinnedId,
  type DisplayedChild,
  type HighlightedTrack,
  type RankKey,
} from "../timelineRows";
import { BaseSchema, Entity, Tracklet, WorkspaceType } from "$lib/types/dataset";

function key(
  id: string,
  firstFrame: number,
  name: string | null = null,
  parentId: string | null = null,
): RankKey {
  return { id, firstFrame, name, parentId };
}

/** The ids of a rank map, by rank. */
function order(ranks: ReadonlyMap<string, number>): string[] {
  return [...ranks].sort((a, b) => a[1] - b[1]).map(([id]) => id);
}

function child(highlighted: "all" | "self" | "none", hidden = false): DisplayedChild {
  return { ui: { displayControl: { hidden, highlighted } } };
}

function track(
  entityId: string,
  highlighted: "all" | "self" | "none",
  topId?: string,
): HighlightedTrack {
  return {
    data: { entity_id: entityId },
    ui: {
      displayControl: { highlighted },
      top_entities: topId ? [{ id: topId }] : undefined,
    },
  };
}

describe("rankTimelineRows", () => {
  it("ranks by first frame, then name, then id, rows without tracks last", () => {
    const ranks = rankTimelineRows([
      key("d", Infinity),
      key("c", 10, "x"),
      key("b", 10, "b"),
      key("a", 0),
    ]);

    expect(order(ranks)).toEqual(["a", "b", "c", "d"]);
    expect([...ranks.values()].sort()).toEqual([0, 1, 2, 3]);
  });

  it("puts unnamed rows after named ones on the same first frame", () => {
    const ranks = rankTimelineRows([key("a", 0), key("b", 10), key("c", 10, "x")]);

    expect(order(ranks)).toEqual(["a", "c", "b"]);
  });

  it("counts an empty name as no name", () => {
    expect(order(rankTimelineRows([key("e", 5, ""), key("f", 5, "zed")]))).toEqual(["f", "e"]);
  });

  it("sorts names in natural order", () => {
    const ranks = rankTimelineRows([key("x1", 0, "car 10"), key("x2", 0, "car 2")]);

    expect(order(ranks)).toEqual(["x2", "x1"]);
  });

  it("breaks ties by id, in natural order", () => {
    const ranks = rankTimelineRows([key("obj10", 3), key("obj2", 3), key("obj1", 3)]);

    expect(order(ranks)).toEqual(["obj1", "obj2", "obj10"]);
  });

  it("sorts a first frame that is not a number like a row without tracks", () => {
    const ranks = rankTimelineRows([key("n", Number.NaN), key("i", Infinity), key("a", 7)]);

    expect(order(ranks)).toEqual(["a", "i", "n"]);
  });

  it("puts sub-entities right after their parent, ranked among themselves", () => {
    const ranks = rankTimelineRows([
      key("b", 10),
      key("w2", 30, null, "a"),
      key("a", 0),
      key("w1", 20, null, "a"),
    ]);

    expect(order(ranks)).toEqual(["a", "w1", "w2", "b"]);
  });

  it("ranks a sub-entity whose parent has no row by its own keys", () => {
    const ranks = rankTimelineRows([
      key("a", 0),
      key("b", 10),
      key("w", 5, null, "ghost"),
      key("v", 7, null, ""),
    ]);

    expect(order(ranks)).toEqual(["a", "w", "v", "b"]);
  });

  it("sorts the sub-entities of one parent by first frame, name and id", () => {
    const ranks = rankTimelineRows([
      key("truck", 3),
      key("never", Infinity, "aaa", "car"),
      key("u", 5, null, "car"),
      key("n10", 5, "wheel 10", "car"),
      key("n2", 5, "wheel 2", "car"),
      key("early", 1, null, "car"),
      key("car", 0),
    ]);

    expect(order(ranks)).toEqual(["car", "early", "n2", "n10", "u", "never", "truck"]);
  });

  it("gives the same ranks whatever the order of the keys", () => {
    const keys = [
      key("car", 0, "car"),
      key("wheel", 4, null, "car"),
      key("door", 4, "door", "car"),
      key("bolt", 1, null, "wheel"),
      key("orphan", 0, "orphan", "ghost"),
      key("idle", Infinity),
    ];
    const expected = ["car", "door", "wheel", "bolt", "orphan", "idle"];
    const permutations = (items: RankKey[]): RankKey[][] =>
      items.length <= 1
        ? [items]
        : items.flatMap((item, index) =>
            permutations(items.filter((_, other) => other !== index)).map((rest) => [
              item,
              ...rest,
            ]),
          );

    const orders = permutations(keys).map((permuted) => order(rankTimelineRows(permuted)));
    expect(orders).toHaveLength(720);
    expect(orders.filter((ids) => ids.join() !== expected.join())).toEqual([]);
  });

  it("puts grand-children after their own parent, before the parent's next sub-entity", () => {
    const ranks = rankTimelineRows([
      key("truck", 10),
      key("door", 20, null, "car"),
      key("bolt", 99, null, "wheel"),
      key("wheel", 15, null, "car"),
      key("car", 0),
    ]);

    expect(order(ranks)).toEqual(["car", "wheel", "bolt", "door", "truck"]);
  });

  it("still ranks entities whose parent chain loops", () => {
    const ranks = rankTimelineRows([
      key("a", 0, null, "b"),
      key("b", 5, null, "a"),
      key("s", 3, null, "s"),
      key("c", 1),
    ]);

    expect(order(ranks)).toEqual(["c", "s", "a", "b"]);
  });

  it("keeps a sub-entity hanging off a parent loop after its parent", () => {
    const ranks = rankTimelineRows([
      key("a", 5, null, "b"),
      key("b", 6, null, "a"),
      key("t", 0, null, "a"),
      key("u", 0, null, "t"),
      key("c", 1),
    ]);

    expect(order(ranks)).toEqual(["c", "a", "t", "u", "b"]);
  });

  it("keeps the first key of a repeated id", () => {
    const ranks = rankTimelineRows([key("a", 0), key("b", 5), key("a", 10)]);

    expect(ranks.size).toBe(2);
    expect(order(ranks)).toEqual(["a", "b"]);
  });

  it("is empty without keys", () => {
    expect(rankTimelineRows([]).size).toBe(0);
  });
});

describe("extendTimelineRanks", () => {
  const ranks = rankTimelineRows([key("a", 0), key("b", 10)]);

  it("keeps the frozen order after a row's first frame moves", () => {
    const retimed = [key("a", 50), key("b", 10)];

    expect(order(rankTimelineRows(retimed))).toEqual(["b", "a"]);
    const extended = extendTimelineRanks(ranks, retimed);
    expect(extended).toBe(ranks);
    expect(orderTimelineRows(["a", "b"], extended, [], false).ids).toEqual(["a", "b"]);
  });

  it("appends a new row last, whatever its first frame", () => {
    const extended = extendTimelineRanks(ranks, [key("a", 50), key("b", 10), key("e", 5)]);

    expect(order(extended)).toEqual(["a", "b", "e"]);
    expect(extended.get("e")).toBe(2);
    expect(extended).not.toBe(ranks);
    expect(ranks.has("e")).toBe(false);
  });

  it("orders new rows among themselves as rankTimelineRows does", () => {
    const extended = extendTimelineRanks(ranks, [
      key("a", 0),
      key("e", 5),
      key("g", 0, null, "e"),
      key("f", 1),
    ]);

    expect(order(extended)).toEqual(["a", "b", "f", "e", "g"]);
    expect([extended.get("f"), extended.get("e"), extended.get("g")]).toEqual([2, 3, 4]);
  });

  it("ranks a new sub-entity of a ranked parent last, by its own keys", () => {
    const extended = extendTimelineRanks(ranks, [key("w", 2, null, "a"), key("a", 0)]);

    expect(order(extended)).toEqual(["a", "b", "w"]);
  });

  it("returns the same Map when no id is new", () => {
    expect(extendTimelineRanks(ranks, [key("b", 10)])).toBe(ranks);
    expect(extendTimelineRanks(ranks, [])).toBe(ranks);
  });

  it("ranks after the highest rank and leaves the given Map unchanged", () => {
    const sparse = new Map([
      ["a", 0],
      ["z", 7],
    ]);

    const extended = extendTimelineRanks(sparse, [key("a", 0), key("e", 5)]);

    expect(extended.get("e")).toBe(8);
    expect(extended.get("z")).toBe(7);
    expect(sparse.has("e")).toBe(false);
  });

  it("starts from 0 without ranks", () => {
    const extended = extendTimelineRanks(new Map(), [key("b", 1), key("a", 0)]);

    expect([...extended]).toEqual([
      ["a", 0],
      ["b", 1],
    ]);
  });
});

describe("orderTimelineRows", () => {
  const ranks = rankTimelineRows([key("a", 0), key("b", 10), key("c", 20), key("d", 30)]);
  const all = ["a", "b", "c", "d"];

  it("lists pinned rows first, in rank order rather than pin order", () => {
    const rows = orderTimelineRows(all, ranks, ["d", "b"], false);

    expect(rows.ids).toEqual(["b", "d", "a", "c"]);
    expect(rows.pinnedCount).toBe(2);
    expect([...rows.pinnedIds]).toEqual(["b", "d"]);
    expect(rows.pinnedOnly).toBe(false);
    expect(rows.candidateCount).toBe(4);
  });

  it("lists only the pinned rows under Pinned-only", () => {
    const rows = orderTimelineRows(all, ranks, ["d", "b"], true);

    expect(rows.ids).toEqual(["b", "d"]);
    expect(rows.pinnedOnly).toBe(true);
    expect(rows.pinnedCount).toBe(2);
    expect(rows.candidateCount).toBe(4);
  });

  it("ignores pins that are not candidates", () => {
    const stale = orderTimelineRows(all, ranks, ["zzz"], true);

    expect(stale.pinnedCount).toBe(0);
    expect(stale.pinnedIds.size).toBe(0);
    expect(stale.pinnedOnly).toBe(false);
    expect(stale.ids).toEqual(all);

    const mixed = orderTimelineRows(all, ranks, ["zzz", "c"], false);
    expect(mixed.ids).toEqual(["c", "a", "b", "d"]);
    expect(mixed.pinnedCount).toBe(1);

    const filtered = orderTimelineRows(all, ranks, ["zzz", "c"], true);
    expect(filtered.ids).toEqual(["c"]);
    expect([...filtered.pinnedIds]).toEqual(["c"]);
    expect(filtered.pinnedOnly).toBe(true);
    expect(filtered.candidateCount).toBe(4);
  });

  it("lists every row under Pinned-only without pins", () => {
    const rows = orderTimelineRows(all, ranks, [], true);

    expect(rows.ids).toEqual(all);
    expect(rows.pinnedOnly).toBe(false);
  });

  it("sorts candidates by rank, ids without a rank last by id", () => {
    const rows = orderTimelineRows(["new10", "d", "new2", "a", "c"], ranks, [], false);

    expect(rows.ids).toEqual(["a", "c", "d", "new2", "new10"]);
  });

  it("puts a pinned candidate without a rank first", () => {
    const rows = orderTimelineRows(["new", ...all], ranks, new Set(["new", "c"]), false);

    expect(rows.ids).toEqual(["c", "new", "a", "b", "d"]);
  });

  it("lists each candidate once and counts each pin once", () => {
    const rows = orderTimelineRows(["b", "a", "b"], ranks, ["b", "b"], false);

    expect(rows.ids).toEqual(["b", "a"]);
    expect(rows.pinnedCount).toBe(1);
    expect(rows.candidateCount).toBe(2);
  });

  it("lists nothing without candidates", () => {
    const rows = orderTimelineRows([], ranks, ["a"], true);

    expect(rows.ids).toEqual([]);
    expect(rows.pinnedCount).toBe(0);
    expect(rows.pinnedOnly).toBe(false);
    expect(rows.candidateCount).toBe(0);
  });
});

describe("sameTimelineRowList", () => {
  const ranks = rankTimelineRows([key("a", 0), key("b", 10), key("c", 20), key("d", 30)]);
  const all = ["a", "b", "c", "d"];

  it("matches lists with the same rows, order and counts", () => {
    const list = orderTimelineRows(all, ranks, ["d"], false);

    expect(sameTimelineRowList(list, orderTimelineRows(all, ranks, ["d"], false))).toBe(true);
    expect(sameTimelineRowList(list, list)).toBe(true);
    expect(sameTimelineRowList(null, null)).toBe(true);
  });

  it("tells apart another order", () => {
    expect(
      sameTimelineRowList(
        orderTimelineRows(all, ranks, ["d"], false),
        orderTimelineRows(all, ranks, ["c"], false),
      ),
    ).toBe(false);
  });

  it("tells apart another pinned count with the same ids", () => {
    const none = orderTimelineRows(all, ranks, [], false);
    const first = orderTimelineRows(all, ranks, ["a"], false);

    expect(first.ids).toEqual(none.ids);
    expect(sameTimelineRowList(none, first)).toBe(false);
  });

  it("tells apart Pinned-only with the same ids", () => {
    expect(
      sameTimelineRowList(
        orderTimelineRows(["a"], ranks, ["a"], true),
        orderTimelineRows(["a"], ranks, ["a"], false),
      ),
    ).toBe(false);
  });

  it("tells apart another candidate count with the same ids", () => {
    expect(
      sameTimelineRowList(
        orderTimelineRows(["a", "b"], ranks, ["a"], true),
        orderTimelineRows(["a"], ranks, ["a"], true),
      ),
    ).toBe(false);
  });

  it("tells apart a missing list", () => {
    expect(sameTimelineRowList(null, orderTimelineRows(all, ranks, [], false))).toBe(false);
  });
});

describe("togglePinnedId", () => {
  it("appends an id that is not pinned", () => {
    expect(togglePinnedId(["a", "b"], "c")).toEqual(["a", "b", "c"]);
    expect(togglePinnedId([], "a")).toEqual(["a"]);
  });

  it("removes an id that is pinned", () => {
    expect(togglePinnedId(["a", "b", "c"], "b")).toEqual(["a", "c"]);
  });

  it("leaves the given list unchanged", () => {
    const ids = ["a"];

    togglePinnedId(ids, "b");
    togglePinnedId(ids, "a");
    expect(ids).toEqual(["a"]);
  });
});

describe("resolveSelectedRow", () => {
  const topIdOf = (id: string) => (id === "wheel" ? "car" : id);

  it("keeps the focused sub-entity row of the selected entity", () => {
    expect(
      resolveSelectedRow({
        selectedTopId: "car",
        focusedRowId: "wheel",
        editedTrackOwnerId: null,
        topIdOf,
      }),
    ).toBe("wheel");
  });

  it("drops a focused row of another entity", () => {
    expect(
      resolveSelectedRow({
        selectedTopId: "truck",
        focusedRowId: "wheel",
        editedTrackOwnerId: null,
        topIdOf,
      }),
    ).toBe("truck");
  });

  it("selects the edited track's own entity without a focused row", () => {
    expect(
      resolveSelectedRow({
        selectedTopId: "car",
        focusedRowId: null,
        editedTrackOwnerId: "wheel",
        topIdOf,
      }),
    ).toBe("wheel");
    expect(
      resolveSelectedRow({
        selectedTopId: "car",
        focusedRowId: "truck",
        editedTrackOwnerId: "wheel",
        topIdOf,
      }),
    ).toBe("wheel");
  });

  it("prefers the focused row to the edited track", () => {
    expect(
      resolveSelectedRow({
        selectedTopId: "car",
        focusedRowId: "car",
        editedTrackOwnerId: "wheel",
        topIdOf,
      }),
    ).toBe("car");
  });

  it("falls back to the selected entity for an unknown row", () => {
    const known = new Map([["wheel", "car"]]);

    expect(
      resolveSelectedRow({
        selectedTopId: "car",
        focusedRowId: "ghost",
        editedTrackOwnerId: "ghost",
        topIdOf: (id) => known.get(id),
      }),
    ).toBe("car");
  });

  it("selects no row when nothing is selected", () => {
    expect(
      resolveSelectedRow({
        selectedTopId: null,
        focusedRowId: "wheel",
        editedTrackOwnerId: "wheel",
        topIdOf,
      }),
    ).toBeNull();
  });
});

describe("storedSelfEntityId", () => {
  it("returns the top-level entity of the first tracklet highlighted as self", () => {
    expect(
      storedSelfEntityId([
        track("truck", "none"),
        track("wheel", "self", "car"),
        track("truck", "self", "truck"),
      ]),
    ).toBe("car");
  });

  it("falls back to the tracklet's entity", () => {
    expect(storedSelfEntityId([track("truck", "self")])).toBe("truck");
    // Shapes created on the canvas can carry an empty list of top entities.
    const created: HighlightedTrack = {
      data: { entity_id: "truck" },
      ui: { displayControl: { highlighted: "self" }, top_entities: [] },
    };
    expect(storedSelfEntityId([created])).toBe("truck");
  });

  it("skips a tracklet highlighted as self that names no entity", () => {
    const orphan: HighlightedTrack = { data: {}, ui: { displayControl: { highlighted: "self" } } };

    expect(storedSelfEntityId([orphan, track("wheel", "self", "car")])).toBe("car");
    expect(storedSelfEntityId([orphan])).toBeNull();
  });

  it("is null without a tracklet highlighted as self", () => {
    expect(storedSelfEntityId([track("a", "all"), track("b", "none")])).toBeNull();
    expect(storedSelfEntityId([])).toBeNull();
  });
});

describe("fusionHighlightState", () => {
  it("is self when a child is self", () => {
    expect(fusionHighlightState([child("all"), child("none"), child("self"), child("none")])).toBe(
      "self",
    );
  });

  it("is none when a child is none and none is self", () => {
    expect(fusionHighlightState([child("all"), child("none")])).toBe("none");
  });

  it("is all otherwise", () => {
    expect(fusionHighlightState([child("all"), child("all")])).toBe("all");
    expect(fusionHighlightState([])).toBe("all");
    expect(fusionHighlightState(undefined)).toBe("all");
  });
});

describe("isHiddenInInspector", () => {
  it("is true when every child is hidden", () => {
    expect(isHiddenInInspector([child("all", true), child("none", true)])).toBe(true);
  });

  it("is false when a child is visible", () => {
    expect(isHiddenInInspector([child("all", true), child("all", false)])).toBe(false);
  });

  it("is false without children", () => {
    expect(isHiddenInInspector([])).toBe(false);
    expect(isHiddenInInspector(undefined)).toBe(false);
  });
});

describe("workspace annotations", () => {
  const NOW = "2026-10-20T00:00:00+00:00";

  function trackedEntity(id: string, parentId: string, top: Entity | null): [Entity, Tracklet] {
    const entity = new Entity({
      id,
      table_info: { name: "entities", group: "entities", base_schema: BaseSchema.Entity },
      created_at: NOW,
      updated_at: NOW,
      data: { item_id: "item-1", parent_id: parentId },
    });
    const tracklet = new Tracklet({
      id: `${id}-track`,
      table_info: { name: "tracklets", group: "annotations", base_schema: BaseSchema.Tracklet },
      created_at: NOW,
      updated_at: NOW,
      data: {
        item_id: "item-1",
        entity_id: id,
        source_type: "ground_truth",
        source_name: "Pixano",
        source_metadata: "{}",
        view_name: "camera",
        inference_metadata: {},
        start_frame: 0,
        end_frame: 4,
        start_timestamp: 0,
        end_timestamp: 4,
      },
    });
    tracklet.ui = {
      datasetItemType: WorkspaceType.VIDEO,
      displayControl: { hidden: true, editing: false, highlighted: "self" },
      childs: [],
      top_entities: [top ?? entity],
    };
    entity.ui.childs = [tracklet];
    return [entity, tracklet];
  }

  it("reads the display state of real entities and tracklets", () => {
    const [car] = trackedEntity("car", "", null);
    const [wheel, wheelTrack] = trackedEntity("wheel", "car", car);

    expect(storedSelfEntityId([wheelTrack])).toBe("car");
    expect(fusionHighlightState(wheel.ui.childs)).toBe("self");
    expect(isHiddenInInspector(wheel.ui.childs)).toBe(true);
  });
});

describe("rowGraphicsOpacity", () => {
  it("dims hidden rows most, then rows dimmed by Fusion", () => {
    expect(rowGraphicsOpacity({ hiddenInInspector: true, fusionDimmed: false })).toBe(0.5);
    expect(rowGraphicsOpacity({ hiddenInInspector: true, fusionDimmed: true })).toBe(0.5);
    expect(rowGraphicsOpacity({ hiddenInInspector: false, fusionDimmed: true })).toBe(0.4);
    expect(rowGraphicsOpacity({ hiddenInInspector: false, fusionDimmed: false })).toBe(1);
  });
});

describe("rowKeyframeLabel", () => {
  it("counts keyframes", () => {
    expect(rowKeyframeLabel(12)).toBe("12 kf");
    expect(rowKeyframeLabel(1)).toBe("1 kf");
    expect(rowKeyframeLabel(0)).toBe("0 kf");
  });
});

describe("timelineEmptyState", () => {
  it("tells no tracks from hidden tracks", () => {
    expect(timelineEmptyState({ trackedCount: 0, visibleCount: 0 })).toBe("no-tracks");
    expect(timelineEmptyState({ trackedCount: 3, visibleCount: 0 })).toBe("all-hidden");
    expect(timelineEmptyState({ trackedCount: 3, visibleCount: 2 })).toBeNull();
  });

  it("has a text for each state", () => {
    expect(TIMELINE_EMPTY_TEXT["no-tracks"]).toBe("No tracked objects in this record yet.");
    expect(TIMELINE_EMPTY_TEXT["all-hidden"]).toBe(
      "All tracks are hidden. Show them from the Entities tab.",
    );
  });
});

describe("cornerLabel", () => {
  it("shows the frame rate and the frame count", () => {
    expect(cornerLabel(30, 200)).toEqual({ fps: "30 fps", frames: "200 frames" });
    expect(cornerLabel(29.97003, 18000)).toEqual({ fps: "29.97 fps", frames: "18000 frames" });
    expect(cornerLabel(12.5, 2)).toEqual({ fps: "12.5 fps", frames: "2 frames" });
    expect(cornerLabel(23.976, 24).fps).toBe("23.98 fps");
  });

  it("names a single frame in the singular", () => {
    expect(cornerLabel(null, 1)).toEqual({ fps: null, frames: "1 frame" });
    expect(cornerLabel(25, 0).frames).toBe("0 frames");
  });

  it("drops an unknown frame rate", () => {
    expect(cornerLabel(null, 200).fps).toBeNull();
    expect(cornerLabel(0, 200).fps).toBeNull();
    expect(cornerLabel(-30, 200).fps).toBeNull();
    expect(cornerLabel(Number.NaN, 200).fps).toBeNull();
    expect(cornerLabel(Number.POSITIVE_INFINITY, 200).fps).toBeNull();
  });
});
