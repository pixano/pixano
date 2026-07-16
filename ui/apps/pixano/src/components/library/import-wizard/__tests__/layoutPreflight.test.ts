/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  classifyMediaName,
  matchesTask,
  preflightLayout,
  toSnakeCase,
  type LayoutPreflight,
} from "../layoutPreflight";

const entries = (...paths: string[]) => paths.map((relPath) => ({ relPath }));

const codes = (layout: LayoutPreflight) => layout.findings.map((finding) => finding.code);

describe("classifyMediaName / matchesTask", () => {
  it("classifies by extension, case-insensitively", () => {
    expect(classifyMediaName("a.JPG")).toBe("image");
    expect(classifyMediaName("v.mp4")).toBe("video");
    expect(classifyMediaName("t.md")).toBe("text");
    expect(classifyMediaName("metadata.jsonl")).toBeNull();
    expect(classifyMediaName(".DS_Store")).toBeNull();
  });

  it("MEL keeps both images and texts; image keeps only images", () => {
    expect(matchesTask("a.jpg", "image_text_entity_linking")).toBe(true);
    expect(matchesTask("a.txt", "image_text_entity_linking")).toBe(true);
    expect(matchesTask("a.mp4", "image_text_entity_linking")).toBe(false);
    expect(matchesTask("a.txt", "image")).toBe(false);
  });
});

describe("toSnakeCase (mirrors the backend)", () => {
  it("lowercases and collapses non-alphanumerics", () => {
    expect(toSnakeCase("My-Left")).toBe("my_left");
    expect(toSnakeCase("Left Cam")).toBe("left_cam");
    expect(toSnakeCase("  left__cam  ")).toBe("left_cam");
  });
});

describe("preflightLayout — happy paths", () => {
  it("flat images: one view named after the kind", () => {
    const layout = preflightLayout(entries("a.jpg", "b.png", "notes.csv"), "image");
    expect(layout.ok).toBe(true);
    expect(layout.views).toEqual([{ name: "image", kind: "image", fileCount: 2 }]);
    expect(layout.splits).toEqual([{ name: "default", recordCount: 2 }]);
    expect(layout.totalRecords).toBe(2);
    expect(layout.ignoredFiles).toBe(1);
  });

  it("per-view folders stem-match into records, missing stems warn", () => {
    const layout = preflightLayout(
      entries("left/a.jpg", "left/b.jpg", "right/a.jpg", "right/b.jpg", "right/c.jpg"),
      "image",
    );
    expect(layout.ok).toBe(true);
    expect(layout.views).toEqual([
      { name: "left", kind: "image", fileCount: 2 },
      { name: "right", kind: "image", fileCount: 3 },
    ]);
    expect(layout.totalRecords).toBe(3);
    const warning = layout.findings.find((finding) => finding.code === "missing_view_file");
    expect(warning?.severity).toBe("warning");
  });

  it("split folders wrap either shape", () => {
    const layout = preflightLayout(
      entries("train/left/a.jpg", "train/right/a.jpg", "val/left/b.jpg", "val/right/b.jpg"),
      "image",
    );
    expect(layout.ok).toBe(true);
    expect(layout.splits).toEqual([
      { name: "train", recordCount: 1 },
      { name: "val", recordCount: 1 },
    ]);
    expect(layout.views.map((view) => view.name).sort()).toEqual(["left", "right"]);
  });

  it("MEL image/ + text/ folders pair up", () => {
    const layout = preflightLayout(
      entries("image/a.jpg", "image/b.jpg", "text/a.txt", "text/b.txt"),
      "image_text_entity_linking",
    );
    expect(layout.ok).toBe(true);
    expect(layout.views).toEqual([
      { name: "image", kind: "image", fileCount: 2 },
      { name: "text", kind: "text", fileCount: 2 },
    ]);
    expect(layout.totalRecords).toBe(2);
  });

  it("nested paths inside a view participate in the stem key", () => {
    const layout = preflightLayout(entries("left/sub/a.jpg", "right/sub/a.jpg"), "image");
    expect(layout.ok).toBe(true);
    expect(layout.totalRecords).toBe(1);
  });
});

describe("preflightLayout — blocking errors (mirror media_only.py)", () => {
  it("mixed media kinds in one folder", () => {
    const layout = preflightLayout(
      entries("pair1/a.jpg", "pair1/a.txt"),
      "image_text_entity_linking",
    );
    expect(layout.ok).toBe(false);
    expect(codes(layout)).toContain("mixed_media_kinds");
    // the MEL restructure hint rides on the message
    const finding = layout.findings.find((item) => item.code === "mixed_media_kinds");
    expect(finding?.message).toContain("separate view folders");
  });

  it("per-record MEL folders are detected and blocked", () => {
    const layout = preflightLayout(
      entries("rec1/a.jpg", "rec1/a.txt", "rec2/b.jpg", "rec2/b.txt"),
      "image_text_entity_linking",
    );
    expect(layout.ok).toBe(false);
    expect(codes(layout)).toContain("mixed_media_kinds");
  });

  it("split names mixed with view folders", () => {
    const layout = preflightLayout(entries("train/a.jpg", "extra/b.jpg"), "image");
    expect(layout.ok).toBe(false);
    expect(codes(layout)).toContain("ambiguous_media_layout");
  });

  it("media directly in the folder AND inside subfolders", () => {
    const layout = preflightLayout(entries("root.jpg", "left/a.jpg"), "image");
    expect(layout.ok).toBe(false);
    expect(codes(layout)).toContain("ambiguous_media_layout");
  });

  it("snake_case view-folder collision", () => {
    const layout = preflightLayout(entries("Left Cam/a.jpg", "left_cam/a.jpg"), "image");
    expect(layout.ok).toBe(false);
    expect(codes(layout)).toContain("view_name_collision");
  });

  it("view folder named like a split", () => {
    const layout = preflightLayout(
      entries("train/test/a.jpg", "train/left/a.jpg", "val/test/a.jpg", "val/left/a.jpg"),
      "image",
    );
    expect(layout.ok).toBe(false);
    expect(codes(layout)).toContain("view_name_reserved");
  });

  it("inconsistent views across splits", () => {
    const layout = preflightLayout(
      entries("train/left/a.jpg", "train/right/a.jpg", "val/left/b.jpg"),
      "image",
    );
    expect(layout.ok).toBe(false);
    expect(codes(layout)).toContain("inconsistent_split_views");
  });

  it("duplicate stems inside one view", () => {
    const flat = preflightLayout(entries("a.jpg", "a.png"), "image");
    expect(flat.ok).toBe(false);
    expect(codes(flat)).toContain("duplicate_view_stem");
    const inView = preflightLayout(entries("left/a.jpg", "left/a.png", "right/a.jpg"), "image");
    expect(inView.ok).toBe(false);
    expect(codes(inView)).toContain("duplicate_view_stem");
  });

  it("MEL without a text folder", () => {
    const layout = preflightLayout(
      entries("image/a.jpg", "image/b.jpg"),
      "image_text_entity_linking",
    );
    expect(layout.ok).toBe(false);
    expect(codes(layout)).toContain("mel_needs_image_and_text");
  });

  it("nothing importable for the task", () => {
    const layout = preflightLayout(entries("a.mp4", "notes.csv"), "image");
    expect(layout.ok).toBe(false);
    expect(codes(layout)).toContain("no_media_found");
  });
});

describe("preflightLayout — warnings", () => {
  it("wrong-kind media becomes an ignored_files warning", () => {
    const layout = preflightLayout(entries("a.jpg", "b.jpg", "clip.mp4"), "image_vqa");
    expect(layout.ok).toBe(true);
    const warning = layout.findings.find((finding) => finding.code === "ignored_files");
    expect(warning?.severity).toBe("warning");
    expect(warning?.message).toContain("1 video file");
    expect(layout.ignoredFiles).toBe(1);
  });

  it("root files beside split folders warn", () => {
    const layout = preflightLayout(entries("stray.jpg", "train/a.jpg"), "image");
    expect(layout.ok).toBe(true);
    expect(codes(layout)).toContain("files_outside_splits");
    expect(layout.totalRecords).toBe(1);
  });

  it("hidden segments are skipped like the backend's dot-dir rule", () => {
    const layout = preflightLayout(entries("a.jpg", ".cache/b.jpg", ".DS_Store"), "image");
    expect(layout.ok).toBe(true);
    expect(layout.totalRecords).toBe(1);
    expect(layout.ignoredFiles).toBe(2);
  });
});
