/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  canAnalyze,
  DEFAULT_FIELDS,
  formatBytes,
  groupFindings,
  isHubId,
  mergeSpec,
  parseAdvancedSpec,
  showsLerobotFields,
} from "../wizardUtils";
import type { ImportPlanResponse } from "$lib/api/restTypes";

const fields = (overrides: Partial<typeof DEFAULT_FIELDS>) => ({ ...DEFAULT_FIELDS, ...overrides });

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

describe("showsLerobotFields", () => {
  it("shows for explicit lerobot or auto-detected hub ids", () => {
    expect(showsLerobotFields(fields({ format: "lerobot" }))).toBe(true);
    expect(showsLerobotFields(fields({ format: "", source: "org/name" }))).toBe(true);
    expect(showsLerobotFields(fields({ format: "coco", source: "org/name" }))).toBe(false);
    expect(showsLerobotFields(fields({ format: "", source: "/local/dir" }))).toBe(false);
  });
});

describe("mergeSpec", () => {
  it("builds the friendly-field spec", () => {
    const spec = mergeSpec(
      fields({
        format: "lerobot",
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

  it("omits defaults entirely", () => {
    expect(mergeSpec(fields({}), "")).toEqual({});
  });

  it("advanced JSON wins over fields, deep on objects", () => {
    const spec = mergeSpec(
      fields({ name: "from_field", format: "coco" }),
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
