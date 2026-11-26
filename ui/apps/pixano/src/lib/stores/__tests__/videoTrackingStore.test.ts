/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import type { Job, JobKind } from "$lib/api/jobsApi";

/** What the tests set of the jobs store the tracking store reads. */
interface JobsStoreDouble {
  launch: Mock;
  cancel: Mock;
  start: Mock;
  stop: Mock;
  probe: Mock;
  list: Job[];
  kinds: JobKind[];
  served: Record<string, string[]>;
  error: string | null;
  unavailable: string | null;
}

const jobs = vi.hoisted((): JobsStoreDouble => ({
  launch: vi.fn(),
  cancel: vi.fn(),
  start: vi.fn(),
  stop: vi.fn(),
  probe: vi.fn(),
  list: [],
  kinds: [],
  served: {},
  error: null,
  unavailable: null,
}));

vi.mock("../jobsStore.svelte", () => ({
  jobsStore: {
    launch: jobs.launch,
    cancel: jobs.cancel,
    start: jobs.start,
    stop: jobs.stop,
    probe: jobs.probe,
    offers: (name: string) => jobs.kinds.some((kind) => kind.name === name),
    get kinds() {
      return jobs.kinds;
    },
    get jobs() {
      return jobs.list;
    },
    get servedModels() {
      return jobs.served;
    },
    get error() {
      return jobs.error;
    },
    get unavailable() {
      return jobs.unavailable;
    },
  },
}));

const { videoTracking } = await import("../videoTrackingStore.svelte");

function job(id: string): Job {
  return {
    id,
    kind: "tracking",
    dataset: "ds",
    state: "running",
    total_tasks: 11,
    done_tasks: 0,
    produced: 0,
    skipped: 0,
    quarantined: 0,
    cancel_requested: false,
    error: null,
    created_at: "2026-11-05T00:00:00Z",
    finalizing: false,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  jobs.list = [];
  jobs.kinds = [];
  jobs.served = {};
  jobs.error = null;
  jobs.unavailable = null;
  videoTracking.jobs = {};
  videoTracking.refusals = {};
  videoTracking.startFrames = {};
  videoTracking.outputs = {};
  videoTracking.output = "masks";
});

describe("videoTracking", () => {
  it("launches the tracking of an object from a frame, and follows its job", async () => {
    jobs.launch.mockResolvedValue(job("j1"));
    jobs.list = [job("j1")];

    const accepted = await videoTracking.track("ds", "record-1", "car", 3, "sam-video");

    expect(accepted).toBe(true);
    expect(jobs.launch).toHaveBeenCalledWith("tracking", "ds", {
      model: "sam-video",
      objects: [{ record_id: "record-1", entity_id: "car", frame_index: 3 }],
    });
    expect(videoTracking.jobOf("car")?.id).toBe("j1");
  });

  it("asks for what the job proposes, and keeps it for the object's card", async () => {
    jobs.launch.mockResolvedValue(job("j1"));

    await videoTracking.track("ds", "record-1", "car", 3, "sam-video", "both");

    expect(jobs.launch).toHaveBeenCalledWith("tracking", "ds", {
      model: "sam-video",
      objects: [{ record_id: "record-1", entity_id: "car", frame_index: 3 }],
      output: "both",
    });
    expect(videoTracking.outputOf("car")).toBe("both");
    expect(videoTracking.outputOf("van")).toBe("masks");
    videoTracking.dismiss("car");
    expect(videoTracking.outputOf("car")).toBe("masks");
  });

  it("knows a job launched without a choice proposes masks", async () => {
    jobs.launch.mockResolvedValue(job("j1"));

    await videoTracking.track("ds", "record-1", "car", 3, "sam-video");

    expect(videoTracking.outputOf("car")).toBe("masks");
  });

  it("offers the choice only where the workers' tracking job declares it", () => {
    jobs.kinds = [{ name: "tracking", params_schema: { properties: { model: {} } } }];
    expect(videoTracking.offersOutputs).toBe(false);

    jobs.kinds = [
      { name: "tracking", params_schema: { properties: { output: { enum: ["masks", "boxes"] } } } },
    ];
    expect(videoTracking.offersOutputs).toBe(true);
  });

  it("follows nothing when the server refuses the job", async () => {
    jobs.launch.mockResolvedValue(null);

    expect(await videoTracking.track("ds", "record-1", "car", 3, "sam-video")).toBe(false);
    expect(videoTracking.jobOf("car")).toBeNull();
  });

  it("keeps why the server refused an object's job, until the object is tracked again", async () => {
    jobs.launch.mockImplementation(() => {
      jobs.error = "object 'car' has no mask nor box on frame 3 to start from";
      return Promise.resolve(null);
    });
    await videoTracking.track("ds", "record-1", "car", 3, "sam-video");

    expect(videoTracking.refusalOf("car")).toBe(
      "object 'car' has no mask nor box on frame 3 to start from",
    );
    expect(videoTracking.refusalOf("van")).toBeNull();

    jobs.launch.mockResolvedValue(job("j1"));
    await videoTracking.track("ds", "record-1", "car", 4, "sam-video");

    expect(videoTracking.refusalOf("car")).toBeNull();
  });

  it("says the queue is missing when that is why nothing was accepted", async () => {
    jobs.launch.mockImplementation(() => {
      jobs.unavailable = "No job queue is configured.";
      return Promise.resolve(null);
    });

    await videoTracking.track("ds", "record-1", "car", 3, "sam-video");

    expect(videoTracking.refusalOf("car")).toBe("No job queue is configured.");
  });

  it("launches one job at a time for an object", async () => {
    let answer: (value: Job) => void = () => undefined;
    jobs.launch.mockReturnValue(new Promise<Job>((resolve) => (answer = resolve)));

    const first = videoTracking.track("ds", "record-1", "car", 3, "sam-video");
    const second = await videoTracking.track("ds", "record-1", "car", 3, "sam-video");
    answer(job("j1"));

    expect(second).toBe(false);
    expect(await first).toBe(true);
    expect(jobs.launch).toHaveBeenCalledTimes(1);
  });

  it("shows the job as it was recorded until the store's list holds it", async () => {
    // A list asked for before the job was submitted, landing after it, leaves it out.
    jobs.launch.mockResolvedValue(job("j1"));
    jobs.list = [];

    await videoTracking.track("ds", "record-1", "car", 3, "sam-video");

    expect(videoTracking.jobOf("car")?.id).toBe("j1");
    jobs.list = [{ ...job("j1"), done_tasks: 5 }];
    expect(videoTracking.jobOf("car")?.done_tasks).toBe(5);
  });

  it("cancels the job following an object", async () => {
    videoTracking.jobs = { car: job("j1") };

    await videoTracking.cancel("car");

    expect(jobs.cancel).toHaveBeenCalledWith("j1");
  });

  it("knows the frame after the one an object is tracked from, until its job's end is shown", async () => {
    jobs.launch.mockResolvedValue(job("j1"));

    await videoTracking.track("ds", "record-1", "car", 3, "sam-video");

    expect(videoTracking.firstTrackedFrame("car")).toBe(4);
    expect(videoTracking.firstTrackedFrame("van")).toBeNull();
    videoTracking.dismiss("car");
    expect(videoTracking.firstTrackedFrame("car")).toBeNull();
  });

  it("knows no first frame for an object whose job the server refused", async () => {
    jobs.launch.mockResolvedValue(null);

    await videoTracking.track("ds", "record-1", "car", 3, "sam-video");

    expect(videoTracking.firstTrackedFrame("car")).toBeNull();
  });

  it("forgets an object's job once its card has shown its end", () => {
    videoTracking.jobs = { car: job("j1"), van: job("j2") };

    videoTracking.dismiss("car");

    expect(Object.keys(videoTracking.jobs)).toEqual(["van"]);
  });

  it("follows the jobs only where a worker runs tracking, asked quietly first", async () => {
    await videoTracking.follow();
    expect(jobs.probe).toHaveBeenCalledTimes(1);
    expect(jobs.start).not.toHaveBeenCalled();

    jobs.kinds = [{ name: "tracking", params_schema: {} }];
    await videoTracking.follow();
    expect(jobs.start).toHaveBeenCalledTimes(1);
  });

  it("does not start following a video closed while it asked", async () => {
    jobs.kinds = [{ name: "tracking", params_schema: {} }];
    let answer: () => void = () => undefined;
    jobs.probe.mockReturnValue(new Promise<void>((resolve) => (answer = resolve)));

    const following = videoTracking.follow();
    videoTracking.unfollow();
    answer();
    await following;

    expect(jobs.start).not.toHaveBeenCalled();
  });

  it("runs the model chosen for the video tools when the inference serves it for tracking", () => {
    jobs.served = { video_mask_generation: ["sam-tiny-video", "sam-small-video"] };

    expect(videoTracking.modelFor("sam-small-video")).toBe("sam-small-video");
    expect(videoTracking.modelFor("sam-image")).toBe("sam-tiny-video");
  });

  it("is available where a worker declared the tracking kind", () => {
    expect(videoTracking.available).toBe(false);
    jobs.kinds = [{ name: "tracking", params_schema: {} }];
    expect(videoTracking.available).toBe(true);
  });
});
