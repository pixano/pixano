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
  embeddingsRequest,
  followUpLines,
  formatBytes,
  groupFindings,
  initialEmbeddingsChoice,
  intentToFormat,
  isHubId,
  mergeSpec,
  nextEmbeddingsChoice,
  offersEmbeddingsChoice,
  parseAdvancedSpec,
  parseEpisodeSelection,
  planHasImages,
  schemaSections,
  setupValidationMessage,
  showsLerobotFields,
  type WizardFields,
} from "../wizardUtils";
import type {
  ImportEmbeddingsOffer,
  ImportPlanResponse,
  InferredSchemaResponse,
  IoJobResponse,
} from "$lib/api/restTypes";

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
      schema: { annotations: ["bbox", "mask", "tracklet"] },
    });
  });

  it("omits defaults entirely for auto-detect", () => {
    expect(mergeSpec(fields({}), "")).toEqual({});
  });

  it.each(["lerobot", "auto"] as const)(
    "includes the annotation schema for %s Hub imports",
    (intent) => {
      const base = fields({ intent, source: "lerobot/robot_tasks", episodes: "0:2" });
      base.lerobot.entityAttrs = [
        { name: "category", type: "str", list: false, required: false, defaultValue: "cup" },
      ];
      base.lerobot.recordAttrs = [
        { name: "reviewed", type: "bool", list: false, required: false, defaultValue: "false" },
      ];
      base.lerobot.annotations = ["bbox", "tracklet"];
      expect(mergeSpec(base, "")).toEqual({
        ...(intent === "lerobot" ? { format: "lerobot" } : {}),
        options: { episodes: "0:2" },
        schema: {
          entity: { attrs: { category: { type: "str", default: "cup" } } },
          record: { attrs: { reviewed: { type: "bool", default: false } } },
          annotations: ["bbox", "tracklet"],
        },
      });
    },
  );

  it("keeps LeRobot and raw schema settings separate when changing intent", () => {
    const base = fields({ intent: "lerobot", source: "/staged/source", maxFrames: "15" });
    base.raw.task = "video";
    base.raw.maxFrames = "20";
    base.raw.fps = "5";
    base.raw.framesMode = "reference";
    base.raw.annotations = ["multi_path"];
    base.raw.recordAttrs = [
      { name: "weather", type: "str", list: false, required: false, defaultValue: "sunny" },
    ];
    base.lerobot.entityAttrs = [
      { name: "category", type: "str", list: false, required: false, defaultValue: "cup" },
    ];
    const lerobotSpec = mergeSpec(base, "");
    expect(lerobotSpec).toEqual({
      format: "lerobot",
      options: { max_frames_per_episode: 15 },
      schema: {
        entity: { attrs: { category: { type: "str", default: "cup" } } },
        annotations: ["bbox", "mask", "tracklet"],
      },
    });

    base.intent = "raw";
    expect(mergeSpec(base, "")).toEqual({
      format: "pixano_jsonl",
      dataset: { workspace: "video" },
      options: { frames: "reference" },
      schema: {
        record: { attrs: { weather: { type: "str", default: "sunny" } } },
        annotations: ["multi_path", "tracklet"],
      },
    });
    base.intent = "lerobot";
    expect(mergeSpec(base, "")).toEqual(lerobotSpec);
  });

  it.each(["coco", "pixano_jsonl", "auto"] as const)(
    "ignores hidden LeRobot schema and options for a local %s source",
    (intent) => {
      const base = fields({ intent, source: "/staged/source", episodes: "0:2", maxFrames: "12" });
      base.lerobot.entityAttrs = [
        { name: "category", type: "str", list: false, required: false, defaultValue: "cup" },
      ];
      expect(mergeSpec(base, "")).toEqual(intent === "auto" ? {} : { format: intent });
    },
  );

  it("honors advanced LeRobot schema and option overrides", () => {
    const base = fields({ intent: "lerobot", source: "org/data", maxFrames: "12" });
    base.lerobot.entityAttrs = [
      { name: "category", type: "str", list: false, required: false, defaultValue: "cup" },
    ];
    expect(
      mergeSpec(
        base,
        JSON.stringify({
          schema: { entity: { attrs: { label: "str" } }, annotations: ["classification"] },
          options: { max_frames_per_episode: 5 },
        }),
      ),
    ).toEqual({
      format: "lerobot",
      schema: { entity: { attrs: { label: "str" } }, annotations: ["classification"] },
      options: { max_frames_per_episode: 5 },
    });
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
    base.raw.annotations = ["bbox", "multi_path"];
    expect(mergeSpec(base, "")).toEqual({
      format: "pixano_jsonl",
      dataset: { workspace: "image" },
      schema: {
        views: { left: { kind: "image" }, right: { kind: "image" } },
        record: { attrs: { weather: { type: "str" } } },
        entity: { attrs: { category: { type: "str" }, tags: { type: "str", collection: true } } },
        annotations: ["bbox", "multi_path"],
      },
    });
  });

  it("builds the raw-videos spec: extract default with cap, reference opt-in", () => {
    const extract = fields({ intent: "raw" });
    extract.raw.task = "video";
    extract.raw.maxFrames = "200";
    extract.raw.fps = "10";
    extract.raw.annotations = ["bbox", "tracklet"];
    expect(mergeSpec(extract, "")).toEqual({
      format: "pixano_jsonl",
      dataset: { workspace: "video" },
      schema: { annotations: ["bbox", "tracklet"] },
      options: { max_frames_per_video: 200, fps: 10 },
    });

    const reference = fields({ intent: "raw" });
    reference.raw.task = "video";
    reference.raw.framesMode = "reference";
    reference.raw.annotations = ["bbox"];
    expect(mergeSpec(reference, "")).toEqual({
      format: "pixano_jsonl",
      dataset: { workspace: "video" },
      schema: { annotations: ["bbox", "tracklet"] },
      options: { frames: "reference" },
    });
  });

  it("builds the raw frame-folders video spec", () => {
    const base = fields({ intent: "raw" });
    base.raw.task = "video";
    base.raw.annotations = ["bbox", "tracklet"];
    base.raw.maxFrames = "20";
    base.raw.fps = "30";
    base.raw.layout = preflightLayout(
      ["front/v1/f0.jpg", "side/v1/f0.jpg"].map((relPath) => ({ relPath })),
      "video",
    );
    expect(mergeSpec(base, "")).toEqual({
      format: "pixano_jsonl",
      dataset: { workspace: "video" },
      schema: {
        views: { front: { kind: "sequence_frames" }, side: { kind: "sequence_frames" } },
        annotations: ["bbox", "tracklet"],
      },
      options: { frames: "folders", max_frames_per_video: 20, fps: 30 },
    });
  });

  it("builds the VQA and MEL specs with their workspaces and locked slots", () => {
    const vqa = fields({ intent: "raw" });
    vqa.raw.task = "image_vqa";
    vqa.raw.annotations = ["message"];
    expect(mergeSpec(vqa, "")).toEqual({
      format: "pixano_jsonl",
      dataset: { workspace: "image_vqa" },
      schema: { annotations: ["message"] },
    });

    const mel = fields({ intent: "raw" });
    mel.raw.task = "image_text_entity_linking";
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
  it.each(["lerobot", "auto"] as const)(
    "gates %s Hub imports on the visible schema, not hidden raw settings",
    (intent) => {
      const base = fields({ intent, source: "org/dataset" });
      base.raw.annotations = [];
      expect(canAnalyze(base, "")).toBe(true);
      base.lerobot.entityAttrs = [
        { name: "Bad Name", type: "str", list: false, required: false, defaultValue: "" },
      ];
      expect(canAnalyze(base, "")).toBe(false);
      base.lerobot.entityAttrs = [];
      base.lerobot.annotations = [];
      expect(canAnalyze(base, "")).toBe(true); // Object tracking is always included.
    },
  );

  it("ignores hidden LeRobot validation when the user changes import type", () => {
    const base = fields({ intent: "raw", source: "/staged/source" });
    base.lerobot.annotations = [];
    expect(canAnalyze(base, "")).toBe(true);
    base.intent = "auto";
    expect(canAnalyze(base, "")).toBe(true);
  });

  it("requires a positive integer frame cap when set for LeRobot", () => {
    const base = fields({ intent: "lerobot", source: "org/data" });
    for (const value of ["0", "-1", "1.5", "oops", "9007199254740993"]) {
      base.maxFrames = value;
      expect(canAnalyze(base, "")).toBe(false);
    }
    for (const value of ["", "1", " 300 "]) {
      base.maxFrames = value;
      expect(canAnalyze(base, "")).toBe(true);
    }
  });

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

describe("setupValidationMessage", () => {
  it("explains missing source, invalid overrides, and visible schema errors", () => {
    const base = fields({ intent: "raw" });
    expect(setupValidationMessage(base, "")).toContain("Choose a source");
    base.source = "/staged/source";
    expect(setupValidationMessage(base, "{bad")).toContain("Advanced JSON");
    base.raw.entityAttrs = [
      { name: "Bad Name", type: "str", list: false, required: false, defaultValue: "" },
    ];
    expect(setupValidationMessage(base, "")).toContain("Bad Name");
    base.raw.entityAttrs = [];
    expect(setupValidationMessage(base, "")).toBe("");
  });
});

describe("wizard episode selection", () => {
  it("serializes explicit numbers as a list and keeps inclusive ranges", () => {
    for (const [input, expected] of [
      ["1, 3,7", [1, 3, 7]],
      ["3", [3]],
      ["1,1", [1]],
      [" 0 : 4 ", "0:4"],
      [":4", ":4"],
      ["2:", "2:"],
    ] as const) {
      expect(parseEpisodeSelection(input)).toEqual({ value: expected, error: "" });
      const spec = mergeSpec(
        fields({ intent: "lerobot", source: "org/robot", episodes: input }),
        "",
      );
      expect(spec.options).toEqual({ episodes: expected });
    }
    expect(parseEpisodeSelection("")).toEqual({ error: "" });
  });

  it("blocks malformed, reversed, negative, or unsafe episode selections", () => {
    for (const episodes of [
      "1,",
      "1:3,5",
      "4:0",
      "-1",
      "1.5",
      "oops",
      "9007199254740993",
      "1:2:3",
    ]) {
      const base = fields({ intent: "lerobot", source: "org/robot", episodes });
      expect(parseEpisodeSelection(episodes).error).toBeTruthy();
      expect(canAnalyze(base, "")).toBe(false);
      expect(setupValidationMessage(base, "")).toContain("episode numbers");
    }
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

describe("embeddings after the import", () => {
  const offer = (overrides: Partial<ImportEmbeddingsOffer> = {}): ImportEmbeddingsOffer => ({
    queue_configured: true,
    available: true,
    reason: null,
    enabled_by_default: true,
    models: ["clip", "siglip"],
    default_model: "siglip",
    ...overrides,
  });
  const planWithViews = (...bases: string[]): ImportPlanResponse =>
    ({
      inferred_schema: {
        views: Object.fromEntries(bases.map((base, index) => [`view${index}`, { base }])),
      },
    }) as never;
  const imagePlan = planWithViews("Image");

  it("a plan holds images when one of its views is a still image", () => {
    expect(planHasImages(imagePlan)).toBe(true);
    expect(planHasImages(planWithViews("Video", "Image"))).toBe(true);
    // A frame belongs to its video: the embeddings job computes still images only.
    expect(planHasImages(planWithViews("SequenceFrame"))).toBe(false);
    expect(planHasImages(planWithViews("Text"))).toBe(false);
    expect(planHasImages(null)).toBe(false);
  });

  it("offers the choice for still images where a job queue is configured", () => {
    expect(offersEmbeddingsChoice(offer(), imagePlan)).toBe(true);
    // Unavailable, it is shown with its reason: a worker or a model is missing.
    expect(offersEmbeddingsChoice(offer({ available: false }), imagePlan)).toBe(true);
    // An installation without jobs never reads a refusal.
    expect(offersEmbeddingsChoice(offer({ queue_configured: false }), imagePlan)).toBe(false);
    expect(offersEmbeddingsChoice(offer(), planWithViews("Video"))).toBe(false);
    expect(offersEmbeddingsChoice(null, imagePlan)).toBe(false);
  });

  it("opens on where the job can run and the server's default says so, with its model", () => {
    expect(initialEmbeddingsChoice(offer())).toEqual({
      compute: true,
      model: "siglip",
      decided: true,
    });
    expect(initialEmbeddingsChoice(offer({ enabled_by_default: false })).compute).toBe(false);
    expect(initialEmbeddingsChoice(offer({ available: false }))).toMatchObject({
      compute: false,
      decided: false,
    });
    expect(initialEmbeddingsChoice(offer({ default_model: null })).model).toBe("clip");
    expect(initialEmbeddingsChoice(offer({ default_model: null, models: [] })).model).toBe("");
  });

  it("read again, the offer keeps what the user chose, whatever it says now", () => {
    const chosen = { compute: false, model: "clip", decided: true };
    const unusable = offer({ available: false, reason: "busy", models: [], default_model: null });

    expect(nextEmbeddingsChoice(chosen, offer())).toEqual(chosen);
    expect(nextEmbeddingsChoice(chosen, unusable)).toEqual(chosen);
    // A model no longer served gives way to the default one.
    expect(nextEmbeddingsChoice(chosen, offer({ models: ["siglip"] }))).toEqual({
      compute: false,
      model: "siglip",
      decided: true,
    });
  });

  it("read again, a choice the user never could make starts from the server's default", () => {
    const never = { compute: false, model: "", decided: false };

    expect(nextEmbeddingsChoice(never, offer())).toEqual({
      compute: true,
      model: "siglip",
      decided: true,
    });
  });

  it("asks for the job with the chosen model", () => {
    const chosen = { compute: true, model: "clip", decided: true };
    expect(embeddingsRequest(chosen, offer(), imagePlan)).toEqual({
      compute_embeddings: true,
      embeddings_model: "clip",
    });
  });

  it("says no when unchecked, without still images or without a model", () => {
    const off = { compute_embeddings: false };
    expect(
      embeddingsRequest({ compute: false, model: "clip", decided: true }, offer(), imagePlan),
    ).toEqual(off);
    expect(
      embeddingsRequest(
        { compute: true, model: "clip", decided: true },
        offer(),
        planWithViews("Text"),
      ),
    ).toEqual(off);
    expect(
      embeddingsRequest({ compute: true, model: "", decided: true }, offer(), imagePlan),
    ).toEqual(off);
  });

  it("sends the user's no even when the job could not run when read again", () => {
    // Unchecked on a usable offer, then Edit setup and Review: the offer is unavailable now.
    let choice = initialEmbeddingsChoice(offer());
    choice = { ...choice, compute: false };
    const unavailable = offer({ available: false, reason: "busy" });
    choice = nextEmbeddingsChoice(choice, unavailable);

    expect(embeddingsRequest(choice, unavailable, imagePlan)).toEqual({
      compute_embeddings: false,
    });
  });

  it("leaves the server to decide until the user could choose", () => {
    // The server checks again when the import starts: the job may run by then.
    const unavailable = offer({ available: false });
    expect(embeddingsRequest(initialEmbeddingsChoice(unavailable), unavailable, imagePlan)).toEqual(
      {},
    );
    expect(
      embeddingsRequest({ compute: false, model: "", decided: false }, null, imagePlan),
    ).toEqual({});
    // A plan that does not say which views it holds is not one without images.
    expect(
      embeddingsRequest({ compute: true, model: "clip", decided: true }, offer(), {
        inferred_schema: null,
      } as never),
    ).toEqual({});
  });

  it("the tray says what became of the job once the import is done", () => {
    const job = (status: string, follow_ups: IoJobResponse["follow_ups"]): IoJobResponse =>
      ({ job_id: "i1", status, progress: {}, error: {}, follow_ups }) as never;
    const queued = { kind: "embeddings", params: { model: "clip" }, job_id: "j9", error: "" };
    const refused = {
      kind: "embeddings",
      params: { model: "clip" },
      job_id: "",
      error: "not queued: no worker runs the embeddings job — start pixano-worker",
    };
    const noModel = {
      kind: "embeddings",
      params: {},
      job_id: "",
      error: "not queued: no embeddings model — name one",
    };
    const pending = { kind: "embeddings", params: { model: "clip" }, job_id: "", error: "" };

    expect(followUpLines(job("done", [queued]))).toEqual([
      {
        text: "Embeddings (clip) queued.",
        notQueued: false,
      },
    ]);
    expect(followUpLines(job("done", [refused]))).toEqual([
      {
        text: "Embeddings (clip) not queued: no worker runs the embeddings job — start pixano-worker",
        notQueued: true,
      },
    ]);
    expect(followUpLines(job("done", [noModel]))).toEqual([
      { text: "Embeddings not queued: no embeddings model — name one", notQueued: true },
    ]);
    expect(followUpLines(job("done", [pending]))).toEqual([
      { text: "Embeddings (clip) not queued.", notQueued: true },
    ]);
    // Nothing to do is no refusal: the statistics of a dataset that holds nothing to count.
    const needless = {
      kind: "statistics",
      params: {},
      job_id: "",
      error: "",
      skipped: "the dataset holds no objects, boxes nor masks to count",
    };
    expect(followUpLines(job("done", [needless]))).toEqual([
      {
        text: "Statistics not needed: the dataset holds no objects, boxes nor masks to count.",
        notQueued: false,
      },
    ]);
    // Nothing until the import is done, and nothing from a server that predates follow-ups.
    expect(followUpLines(job("running", [refused]))).toEqual([]);
    expect(followUpLines(job("done", undefined))).toEqual([]);
  });

  it("the tray says what became of each job a follow-up became, on a line of its own", () => {
    const job = (follow_ups: IoJobResponse["follow_ups"]): IoJobResponse =>
      ({ job_id: "i1", status: "done", progress: {}, error: {}, follow_ups }) as never;
    const clip = { kind: "embeddings", params: { model: "clip" }, job_id: "j9", error: "" };
    const siglip = {
      kind: "embeddings",
      params: { model: "siglip" },
      job_id: "",
      error: "not queued: the job queue cannot be read",
    };

    expect(followUpLines(job([clip, siglip]))).toEqual([
      { text: "Embeddings (clip) queued.", notQueued: false },
      { text: "Embeddings (siglip) not queued: the job queue cannot be read", notQueued: true },
    ]);
  });
});
