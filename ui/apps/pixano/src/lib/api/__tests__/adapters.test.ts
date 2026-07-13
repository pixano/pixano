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
