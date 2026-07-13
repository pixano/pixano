/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { preflightLayout } from "../layoutPreflight";
import {
  canAnalyze,
  DEFAULT_FIELDS,
  formatBytes,
  groupFindings,
  intentToFormat,
  isHubId,
  mergeSpec,
  parseAdvancedSpec,
  schemaSections,
  showsLerobotFields,
  type WizardFields,
} from "../wizardUtils";
import type { ImportPlanResponse, InferredSchemaResponse } from "$lib/api/restTypes";

const fields = (overrides: Partial<WizardFields>): WizardFields => ({
  ...structuredClone(DEFAULT_FIELDS),
  ...overrides,
});

describe("isHubId", () => {
  it("accepts org/name ids and rejects paths", () => {
    expect(isHubId("lerobot/aloha_sim_insertion_scripted")).toBe(true);
    expect(isHubId("nvidia/BridgeData2_LeRobot_v3")).toBe(true);
    expect(isHubId("/data/my/folder")).toBe(false);
    expect(isHubId("./relative")).toBe(false);
    expect(isHubId("plainname")).toBe(false);
    expect(isHubId("a/b/c")).toBe(false);
  });
});

describe("intentToFormat", () => {
  it("maps intents onto backend formats", () => {
    expect(intentToFormat("raw")).toBe("pixano_jsonl");
    expect(intentToFormat("pixano_jsonl")).toBe("pixano_jsonl");
    expect(intentToFormat("coco")).toBe("coco");
    expect(intentToFormat("lerobot")).toBe("lerobot");
    expect(intentToFormat("auto")).toBe("");
  });
});

describe("showsLerobotFields", () => {
  it("shows for explicit lerobot or auto-detected hub ids", () => {
    expect(showsLerobotFields(fields({ intent: "lerobot" }))).toBe(true);
    expect(showsLerobotFields(fields({ intent: "auto", source: "org/name" }))).toBe(true);
    expect(showsLerobotFields(fields({ intent: "coco", source: "org/name" }))).toBe(false);
    expect(showsLerobotFields(fields({ intent: "auto", source: "/local/dir" }))).toBe(false);
  });
});

describe("mergeSpec", () => {
  it("builds the lerobot spec", () => {
    const spec = mergeSpec(
      fields({
        intent: "lerobot",
        name: "My DS",
        mode: "overwrite",
        media: "uri",
        episodes: "0:4",
        maxFrames: "300",
      }),
      "",
    );
    expect(spec).toEqual({
      format: "lerobot",
      mode: "overwrite",
      media: { mode: "uri" },
      dataset: { name: "My DS" },
      options: { episodes: "0:4", max_frames_per_episode: 300 },
    });
  });

  it("omits defaults entirely for auto-detect", () => {
    expect(mergeSpec(fields({}), "")).toEqual({});
  });

  it("builds the raw multi-view image spec: preflight views + record/entity attrs", () => {
    const base = fields({ intent: "raw" });
    base.raw.layout = preflightLayout(
      ["left/a.jpg", "right/a.jpg"].map((relPath) => ({ relPath })),
      "image",
    );
    base.raw.recordAttrs = [
      { name: "weather", type: "str", list: false, required: false, defaultValue: "" },
    ];
    base.raw.entityAttrs = [
      { name: "category", type: "str", list: false, required: false, defaultValue: "" },
      { name: "tags", type: "str", list: true, required: false, defaultValue: "" },
    ];
    base.raw.annotations = ["bbox", "classification"];
    expect(mergeSpec(base, "")).toEqual({
      format: "pixano_jsonl",
      dataset: { workspace: "image" },
      schema: {
        views: { left: { kind: "image" }, right: { kind: "image" } },
        record: { attrs: { weather: { type: "str" } } },
        entity: { attrs: { category: { type: "str" }, tags: { type: "str", collection: true } } },
        annotations: ["bbox", "classification"],
      },
    });
  });

  it("builds the raw-videos spec: extract default with cap, reference opt-in", () => {
    const extract = fields({ intent: "raw" });
    extract.raw.useCase = "video";
    extract.raw.maxFrames = "200";
    extract.raw.annotations = ["bbox", "tracklet"];
    expect(mergeSpec(extract, "")).toEqual({
      format: "pixano_jsonl",
      dataset: { workspace: "video" },
      schema: { annotations: ["bbox", "tracklet"] },
      options: { max_frames_per_video: 200 },
    });

    const reference = fields({ intent: "raw" });
    reference.raw.useCase = "video";
    reference.raw.framesMode = "reference";
    reference.raw.annotations = ["bbox"];
    expect(mergeSpec(reference, "")).toEqual({
      format: "pixano_jsonl",
      dataset: { workspace: "video" },
      schema: { annotations: ["bbox"] },
      options: { frames: "reference" },
    });
  });

  it("builds the VQA and MEL specs with their workspaces and locked slots", () => {
    const vqa = fields({ intent: "raw" });
    vqa.raw.useCase = "image_vqa";
    vqa.raw.annotations = ["message"];
    expect(mergeSpec(vqa, "")).toEqual({
      format: "pixano_jsonl",
      dataset: { workspace: "image_vqa" },
      schema: { annotations: ["message"] },
    });

    const mel = fields({ intent: "raw" });
    mel.raw.useCase = "image_text_entity_linking";
    mel.raw.annotations = ["text_span", "bbox", "mask"];
    mel.raw.layout = preflightLayout(
      ["image/a.jpg", "text/a.txt"].map((relPath) => ({ relPath })),
      "image_text_entity_linking",
    );
    expect(mergeSpec(mel, "")).toEqual({
      format: "pixano_jsonl",
      dataset: { workspace: "image_text_entity_linking" },
      schema: {
        views: { image: { kind: "image" }, text: { kind: "text" } },
        annotations: ["text_span", "bbox", "mask"],
      },
    });
  });

  it("ignores lerobot options outside lerobot intents and raw media mode", () => {
    const spec = mergeSpec(fields({ intent: "coco", episodes: "0:4", media: "uri" }), "");
    expect(spec).toEqual({ format: "coco", media: { mode: "uri" } });
    const raw = fields({ intent: "raw", media: "uri" });
    expect(mergeSpec(raw, "").media).toBeUndefined();
  });

  it("defaults the dataset name to the uploaded folder's name", () => {
    const spec = mergeSpec(fields({ intent: "coco", sourceLabel: "flir_adas" }), "");
    expect(spec.dataset).toEqual({ name: "flir_adas" });
    const named = mergeSpec(
      fields({ intent: "coco", sourceLabel: "flir_adas", name: "My DS" }),
      "",
    );
    expect(named.dataset).toEqual({ name: "My DS" });
  });

  it("advanced JSON wins over fields, deep on objects", () => {
    const spec = mergeSpec(
      fields({ name: "from_field", intent: "coco" }),
      JSON.stringify({
        dataset: { workspace: "image" },
        format: "pixano_jsonl",
        schema: { annotations: ["bbox"] },
      }),
    );
    expect(spec.format).toBe("pixano_jsonl");
    expect(spec.dataset).toEqual({ name: "from_field", workspace: "image" });
    expect(spec.schema).toEqual({ annotations: ["bbox"] });
  });
});

describe("schemaSections", () => {
  it("orders Views / Record / Entity / Annotations and flattens attrs", () => {
    const schema: InferredSchemaResponse = {
      workspace: "image",
      views: { left: { base: "Image", fields: {} }, right: { base: "Image", fields: {} } },
      record: { base: "Record", fields: {} },
      entity: {
        base: "Entity",
        name: "CustomEntity",
        fields: {
          category: { type: "str", collection: false, required: false },
          tags: { type: "str", collection: true, required: false },
        },
      },
      bbox: { base: "BBox", fields: {} },
      classification: { base: "Classification", fields: {} },
    };
    const sections = schemaSections(schema);
    expect(sections.map((s) => s.title)).toEqual(["Views", "Record", "Entity", "Annotations"]);
    expect(sections[0].entries.map((e) => e.name)).toEqual(["left", "right"]);
    const entity = sections[2].entries[0];
    expect(entity.base).toBe("Entity");
    expect(entity.attrs).toEqual([
      { name: "category", type: "str", collection: false, required: false },
      { name: "tags", type: "str", collection: true, required: false },
    ]);
    expect(sections[3].entries.map((e) => e.name)).toEqual(["bbox", "classification"]);
  });
});

describe("parseAdvancedSpec", () => {
  it("accepts empty, rejects non-objects and bad JSON", () => {
    expect(parseAdvancedSpec("")).toEqual({ value: null, error: "" });
    expect(parseAdvancedSpec("[1]").error).toContain("JSON object");
    expect(parseAdvancedSpec("{oops").error).toBeTruthy();
    expect(parseAdvancedSpec('{"a": 1}')).toEqual({ value: { a: 1 }, error: "" });
  });
});

describe("groupFindings", () => {
  it("splits by severity", () => {
    const plan = {
      report: {
        findings: {
          a: { code: "a", severity: "error", count: 2, samples: [], suggestion: "" },
          b: { code: "b", severity: "warning", count: 1, samples: [], suggestion: "" },
        },
      },
    } as unknown as ImportPlanResponse;
    const grouped = groupFindings(plan);
    expect(grouped.errors.map((f) => f.code)).toEqual(["a"]);
    expect(grouped.warnings.map((f) => f.code)).toEqual(["b"]);
  });
});

describe("formatBytes", () => {
  it("humanizes", () => {
    expect(formatBytes(null)).toBe("");
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatBytes(160 * 1024 * 1024)).toBe("160 MB");
  });
});

describe("canAnalyze", () => {
  it("needs a source and valid advanced JSON", () => {
    expect(canAnalyze(fields({}), "")).toBe(false);
    expect(canAnalyze(fields({ source: "/data" }), "")).toBe(true);
    expect(canAnalyze(fields({ source: "/data" }), "{bad")).toBe(false);
  });

  it("gates on the raw form when the intent is raw", () => {
    const bad = fields({ intent: "raw", source: "/data" });
    bad.raw.entityAttrs = [
      { name: "Bad Name", type: "str", list: false, required: false, defaultValue: "" },
    ];
    expect(canAnalyze(bad, "")).toBe(false);
    const good = fields({ intent: "raw", source: "/data" });
    good.raw.entityAttrs = [
      { name: "category", type: "str", list: false, required: false, defaultValue: "" },
    ];
    expect(canAnalyze(good, "")).toBe(true);
  });

  it("gates on a failed layout preflight", () => {
    const blocked = fields({ intent: "raw", source: "/data" });
    blocked.raw.layout = preflightLayout(
      ["Left Cam/a.jpg", "left_cam/a.jpg"].map((relPath) => ({ relPath })),
      "image",
    );
    expect(blocked.raw.layout.ok).toBe(false);
    expect(canAnalyze(blocked, "")).toBe(false);
  });
});

describe("background job tracking", () => {
  const makeEntry = (status: string, overrides = {}) =>
    ({
      jobId: "j1",
      dataset: "ds",
      job: { job_id: "j1", status, progress: {}, error: {} },
      cancelRequested: false,
      dismissed: false,
      ...overrides,
    }) as never;

  it("applyJobUpdate flags completion exactly once", async () => {
    const { applyJobUpdate } = await import("../wizardUtils");
    const running = [makeEntry("running")];
    const first = applyJobUpdate(running, {
      job_id: "j1",
      status: "done",
      progress: {},
      error: {},
    } as never);
    expect(first.completedNow).toBe(true);
    const second = applyJobUpdate(first.entries, {
      job_id: "j1",
      status: "done",
      progress: {},
      error: {},
    } as never);
    expect(second.completedNow).toBe(false); // already terminal: no second refresh
  });

  it("errors are terminal but do not trigger a library refresh", async () => {
    const { applyJobUpdate, isTerminalJob } = await import("../wizardUtils");
    const result = applyJobUpdate([makeEntry("running")], {
      job_id: "j1",
      status: "error",
      progress: {},
      error: { message: "boom" },
    } as never);
    expect(result.completedNow).toBe(false);
    expect(isTerminalJob("error")).toBe(true);
  });

  it("active/visible selectors partition entries", async () => {
    const { activeJobEntries, visibleJobEntries } = await import("../wizardUtils");
    const entries = [makeEntry("running"), makeEntry("done", { jobId: "j2", dismissed: true })];
    expect(activeJobEntries(entries).map((entry) => entry.jobId)).toEqual(["j1"]);
    expect(visibleJobEntries(entries).map((entry) => entry.jobId)).toEqual(["j1"]);
  });

  it("jobStateLabel reflects cancel-requested and terminal states", async () => {
    const { jobStateLabel } = await import("../wizardUtils");
    expect(jobStateLabel(makeEntry("running", { cancelRequested: true }))).toBe("Cancelling…");
    expect(jobStateLabel(makeEntry("done"))).toBe("Imported");
    expect(jobStateLabel(makeEntry("interrupted"))).toBe("Failed");
  });
});
