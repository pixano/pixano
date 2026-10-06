/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it, vi } from "vitest";

import { TextExtension } from "../TextExtension.js";
import type { DatasetGateway } from "$lib/workspace/datasetGateway.js";

function makeSeedArgs(overrides: { base?: string; content?: string | undefined } = {}) {
  const loadTextByLogicalName = vi.fn(() =>
    Promise.resolve(
      overrides.content === undefined
        ? null
        : { id: "text-1", record_id: "rec-1", content: overrides.content },
    ),
  );
  return {
    loadTextByLogicalName,
    args: {
      datasetId: "ds-1",
      recordId: "rec-1",
      viewName: "caption",
      viewDef: { base: overrides.base ?? "Text" },
      gateway: { loadTextByLogicalName } as unknown as DatasetGateway,
    },
  };
}

describe("TextExtension.addRecordSeed", () => {
  it("fetches the text view and hands its content to the widget", async () => {
    const { args, loadTextByLogicalName } = makeSeedArgs({ content: "Once upon a time" });

    // Before this the seed claimed the view but fetched nothing, so the widget
    // rendered "No Text Data" on every record.
    const seed = await TextExtension.config.addRecordSeed!(args as never);

    expect(loadTextByLogicalName).toHaveBeenCalledWith("ds-1", "rec-1", "caption");
    expect(seed?.data).toEqual({ content: "Once upon a time" });
  });

  it("declares the view, so annotation seed loaders can resolve against it", async () => {
    const { args } = makeSeedArgs({ content: "text" });

    const seed = await TextExtension.config.addRecordSeed!(args as never);

    expect(seed?.view).toMatchObject({ id: "text-1", logicalName: "caption" });
    expect(seed?.options).toMatchObject({ datasetId: "ds-1", recordId: "rec-1", viewId: "text-1" });
  });

  it("yields empty content rather than nothing when the record has no text row", async () => {
    const { args } = makeSeedArgs({ content: undefined });

    // The view exists in the schema but this record has no row for it: the
    // widget should open empty, not refuse to mount.
    const seed = await TextExtension.config.addRecordSeed!(args as never);

    expect(seed?.data).toEqual({ content: "" });
  });

  it("claims nothing but Text views", async () => {
    const { args, loadTextByLogicalName } = makeSeedArgs({ base: "Image", content: "x" });

    expect(await TextExtension.config.addRecordSeed!(args as never)).toBeNull();
    expect(loadTextByLogicalName).not.toHaveBeenCalled();
  });
});
