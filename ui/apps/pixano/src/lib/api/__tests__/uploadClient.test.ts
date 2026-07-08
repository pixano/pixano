/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { splitFolderSelection } from "../uploadClient";

const fakeFile = (webkitRelativePath: string, size = 10) =>
  ({ webkitRelativePath, name: webkitRelativePath.split("/").pop(), size }) as unknown as File;

describe("splitFolderSelection", () => {
  it("strips the picked folder's name and keeps nested structure", () => {
    const selection = splitFolderSelection([
      fakeFile("my_dataset/left/a.jpg", 100),
      fakeFile("my_dataset/right/a.jpg", 200),
      fakeFile("my_dataset/dataset.yaml", 5),
    ]);
    expect(selection.folderName).toBe("my_dataset");
    expect(selection.entries.map((e) => e.relPath)).toEqual([
      "left/a.jpg",
      "right/a.jpg",
      "dataset.yaml",
    ]);
    expect(selection.totalBytes).toBe(305);
  });

  it("falls back to bare names when webkitRelativePath is absent", () => {
    const selection = splitFolderSelection([fakeFile("a.jpg", 1)]);
    expect(selection.folderName).toBe("");
    expect(selection.entries.map((e) => e.relPath)).toEqual(["a.jpg"]);
  });

  it("returns an empty selection for no files", () => {
    const selection = splitFolderSelection([]);
    expect(selection.entries).toEqual([]);
    expect(selection.totalBytes).toBe(0);
  });
});
