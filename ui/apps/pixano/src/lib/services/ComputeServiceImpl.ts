/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type {
  CancellationToken,
  ComputeJob,
  ComputeJobDescriptor,
  ComputeJobStatus,
  ComputeService,
  Unsubscribe,
} from "$lib/types/services";

// --------------- CancellationToken Implementation ---------------

class CancellationTokenImpl implements CancellationToken {
  private _isCancelled = false;
  private readonly callbacks: Array<() => void> = [];

  get isCancelled(): boolean {
    return this._isCancelled;
  }

  throwIfCancelled(): void {
    if (this._isCancelled) {
      throw new Error("Operation cancelled");
    }
  }

  onCancel(callback: () => void): Unsubscribe {
    if (this._isCancelled) {
      callback();
      return () => {};
    }
    this.callbacks.push(callback);
    return () => {
      const idx = this.callbacks.indexOf(callback);
      if (idx >= 0) this.callbacks.splice(idx, 1);
    };
  }

  cancel(): void {
    if (this._isCancelled) return;
    this._isCancelled = true;
    for (const cb of this.callbacks) {
      try {
        cb();
      } catch {
        // Ignore callback errors
      }
    }
    this.callbacks.length = 0;
  }
}

// --------------- ComputeJob Implementation ---------------

class ComputeJobImpl<T> implements ComputeJob<T> {
  readonly id: string;
  private _status: ComputeJobStatus = "pending";
  private _progress = 0;
  readonly result: Promise<T>;
  private readonly token: CancellationTokenImpl;
  private readonly progressCallbacks: Array<(progress: number) => void> = [];

  constructor(descriptor: ComputeJobDescriptor<T>) {
    this.id = descriptor.id;
    this.token = new CancellationTokenImpl();

    this.result = this.run(descriptor);
  }

  get status(): ComputeJobStatus {
    return this._status;
  }

  get progress(): number {
    return this._progress;
  }

  cancel(): void {
    if (this._status === "pending" || this._status === "running") {
      this.token.cancel();
      this._status = "cancelled";
    }
  }

  onProgress(callback: (progress: number) => void): Unsubscribe {
    this.progressCallbacks.push(callback);
    return () => {
      const idx = this.progressCallbacks.indexOf(callback);
      if (idx >= 0) this.progressCallbacks.splice(idx, 1);
    };
  }

  private async run(descriptor: ComputeJobDescriptor<T>): Promise<T> {
    this._status = "running";
    try {
      const result = await descriptor.run(this.token);
      if (this.token.isCancelled) {
        this._status = "cancelled";
        throw new Error("Job cancelled");
      }
      this._status = "completed";
      this._progress = 1;
      this.notifyProgress(1);
      return result;
    } catch (error) {
      if (this._status !== "cancelled") {
        this._status = "failed";
      }
      throw error;
    }
  }

  private notifyProgress(progress: number): void {
    this._progress = progress;
    for (const cb of this.progressCallbacks) {
      try {
        cb(progress);
      } catch {
        // Ignore callback errors
      }
    }
  }
}

// --------------- ComputeService Implementation ---------------

/**
 * Manages compute jobs with progress tracking and cancellation.
 */
export class ComputeServiceImpl implements ComputeService {
  private readonly jobs = new Map<string, ComputeJob>();

  submit<T>(descriptor: ComputeJobDescriptor<T>): ComputeJob<T> {
    if (this.jobs.has(descriptor.id)) {
      throw new Error(`Job already exists: ${descriptor.id}`);
    }

    const job = new ComputeJobImpl(descriptor);
    this.jobs.set(descriptor.id, job as ComputeJob);

    // Auto-cleanup completed jobs
    void job.result.catch((error: unknown) => {
      console.warn(`[ComputeService] Job ${descriptor.id} failed:`, error);
    }).finally(() => {
      // Keep job in map for status queries, but could add TTL cleanup
    });

    return job;
  }

  cancel(jobId: string): void {
    this.jobs.get(jobId)?.cancel();
  }

  getJob(jobId: string): ComputeJob | undefined {
    return this.jobs.get(jobId);
  }

  getActiveJobs(): ReadonlyArray<ComputeJob> {
    return [...this.jobs.values()].filter(
      (j) => j.status === "pending" || j.status === "running",
    );
  }
}
