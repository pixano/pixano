/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { matchesTask, matchesUpload } from "$components/library/import-wizard/layoutPreflight";
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

describe("filterSelection with matchesTask", () => {
  const selection = splitFolderSelection([
    fakeFile("set/left/a.jpg", 100),
    fakeFile("set/right/a.JPG", 100),
    fakeFile("set/metadata.jsonl", 20),
    fakeFile("set/.DS_Store", 5),
    fakeFile("set/notes.txt", 10),
    fakeFile("set/clip.mp4", 50),
  ]);

  it("drops the stray metadata.jsonl and junk for an image import", () => {
    const filtered = filterSelection(selection, (name) => matchesTask(name, "image"));
    expect(filtered.entries.map((e) => e.relPath)).toEqual(["left/a.jpg", "right/a.JPG"]);
    expect(filtered.totalBytes).toBe(200); // metadata.jsonl / .DS_Store / notes.txt excluded
    expect(filtered.folderName).toBe("set");
  });

  it("keeps BOTH images and texts for a MEL import, dropping the rest", () => {
    const filtered = filterSelection(selection, (name) =>
      matchesTask(name, "image_text_entity_linking"),
    );
    expect(filtered.entries.map((e) => e.relPath)).toEqual([
      "left/a.jpg",
      "right/a.JPG",
      "notes.txt",
    ]);
    expect(filtered.totalBytes).toBe(210);
  });

  it("yields an empty selection when nothing matches (caller shows an error)", () => {
    const noVideos = splitFolderSelection([fakeFile("set/a.jpg", 1)]);
    const filtered = filterSelection(noVideos, (name) => matchesTask(name, "video"));
    expect(filtered.entries).toEqual([]);
  });

  it("keeps only frame images for a folders-encoding video upload", () => {
    const filtered = filterSelection(selection, (name) => matchesUpload(name, "video", "folders"));
    expect(filtered.entries.map((e) => e.relPath)).toEqual(["left/a.jpg", "right/a.JPG"]);
  });
});
