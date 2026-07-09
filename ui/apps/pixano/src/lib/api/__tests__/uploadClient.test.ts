/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { matchesMediaKind } from "$components/library/import-wizard/rawSchema";
import { describe, expect, it } from "vitest";

import { filterSelection, splitFolderSelection } from "../uploadClient";

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

describe("filterSelection with matchesMediaKind", () => {
  const selection = splitFolderSelection([
    fakeFile("set/left/a.jpg", 100),
    fakeFile("set/right/a.JPG", 100),
    fakeFile("set/metadata.jsonl", 20),
    fakeFile("set/.DS_Store", 5),
    fakeFile("set/notes.txt", 10),
  ]);

  it("drops the stray metadata.jsonl and junk for an images import", () => {
    const filtered = filterSelection(selection, (name) => matchesMediaKind(name, "images"));
    expect(filtered.entries.map((e) => e.relPath)).toEqual(["left/a.jpg", "right/a.JPG"]);
    expect(filtered.totalBytes).toBe(200); // metadata.jsonl / .DS_Store / notes.txt excluded
    expect(filtered.folderName).toBe("set");
  });

  it("keeps only text files for a text import", () => {
    const filtered = filterSelection(selection, (name) => matchesMediaKind(name, "texts"));
    expect(filtered.entries.map((e) => e.relPath)).toEqual(["notes.txt"]);
  });

  it("yields an empty selection when nothing matches (caller shows an error)", () => {
    const filtered = filterSelection(selection, (name) => matchesMediaKind(name, "videos"));
    expect(filtered.entries).toEqual([]);
  });
});
