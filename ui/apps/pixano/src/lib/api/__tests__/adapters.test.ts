/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { toDatasetBrowser } from "../adapters";
import type { PaginatedResponse, RecordResponse } from "../restTypes";

const paginated = (items: RecordResponse[]): PaginatedResponse<RecordResponse> => ({
  items,
  total: items.length,
  limit: 20,
  offset: 0,
});

const columnType = (browser: ReturnType<typeof toDatasetBrowser>, name: string) =>
  browser.table_data.columns.find((col) => col.name === name)?.type;

describe("toDatasetBrowser list attributes", () => {
  it("renders a string[] attribute as a joined 'list' column", () => {
    const browser = toDatasetBrowser(
      "ds",
      paginated([{ id: "0", split: "train", episode_index: 3, tasks: ["pick up the block"] }]),
    );
    expect(columnType(browser, "tasks")).toBe("list");
    expect(browser.table_data.rows[0].tasks).toBe("pick up the block");
    // scalars keep their inferred types
    expect(columnType(browser, "episode_index")).toBe("int");
    expect(columnType(browser, "split")).toBe("str");
    expect(browser.table_data.rows[0].episode_index).toBe(3);
  });

  it("joins multiple list items with '; '", () => {
    const browser = toDatasetBrowser("ds", paginated([{ id: "0", tasks: ["a", "b"] }]));
    expect(browser.table_data.rows[0].tasks).toBe("a; b");
  });

  it("keeps an empty list as an empty-string column", () => {
    const browser = toDatasetBrowser("ds", paginated([{ id: "0", tasks: [] }]));
    expect(columnType(browser, "tasks")).toBe("list");
    expect(browser.table_data.rows[0].tasks).toBe("");
  });

  it("preserves the backend row order (no client-side re-sort) and drops semantic_search", () => {
    const browser = toDatasetBrowser("ds", paginated([{ id: "b" }, { id: "a" }, { id: "c" }]));
    // Rows must keep the server-sent order, not be re-sorted client-side.
    expect(browser.table_data.rows.map((r) => r.id)).toEqual(["b", "a", "c"]);
    expect("semantic_search" in browser).toBe(false);
  });

  it("infers bool columns and never turns view_previews into a record column", () => {
    const browser = toDatasetBrowser(
      "ds",
      paginated([
        {
          id: "0",
          reviewed: true,
          view_previews: {
            image: { resource: "views", id: "v0", kind: "image", preview_url: "/blob/v0" },
          },
        },
      ]),
    );
    expect(columnType(browser, "reviewed")).toBe("bool");
    expect(columnType(browser, "view_previews")).toBeUndefined();
    // the preview surfaces as its own column, typed by the preview kind
    expect(columnType(browser, "image")).toBe("image");
    expect(browser.table_data.rows[0].image).toBe("/blob/v0");
  });
});

describe("toDatasetBrowser card_data", () => {
  it("builds one card per record with previews, badges and custom attrs", () => {
    const browser = toDatasetBrowser(
      "ds",
      paginated([
        {
          id: "r0",
          split: "train",
          status: "new",
          created_at: "2026-01-01",
          scene: "urban",
          view_previews: {
            rgb: { resource: "images", id: "i0", kind: "image", preview_url: "/i0?size=256" },
            thermal: { resource: "images", id: "i1", kind: "image", preview_url: "/i1?size=256" },
          },
        },
      ]),
    );
    const card = browser.card_data?.[0];
    if (!card) throw new Error("card_data missing");
    expect(card.id).toBe("r0");
    expect(card.split).toBe("train");
    expect(card.status).toBe("new");
    expect(card.previews.map((p) => p.name)).toEqual(["rgb", "thermal"]);
    expect(card.previews[0].url).toBe("/i0?size=256");
    // system fields are excluded from the attr line; customs are kept
    expect(card.attrs).toEqual({ scene: "urban" });
  });

  it("maps a text preview to an excerpt (card) and a str column (table)", () => {
    const browser = toDatasetBrowser(
      "ds",
      paginated([
        {
          id: "r0",
          view_previews: {
            text: { resource: "texts", id: "t0", kind: "text", preview_url: "", excerpt: "lorem" },
          },
        },
      ]),
    );
    const card = browser.card_data?.[0];
    if (!card) throw new Error("card_data missing");
    expect(card.previews[0]).toMatchObject({ kind: "text", resource: "texts", excerpt: "lorem" });
    // the table shows the excerpt string, not an empty preview URL
    expect(columnType(browser, "text")).toBe("str");
    expect(browser.table_data.rows[0].text).toBe("lorem");
  });

  it("carries _distance into the card in ranked mode", () => {
    const browser = toDatasetBrowser("ds", paginated([{ id: "r0", _distance: 0.42 }]));
    expect(browser.card_data?.[0].distance).toBe(0.42);
    expect(browser.card_data?.[0].attrs).toEqual({});
  });
});
