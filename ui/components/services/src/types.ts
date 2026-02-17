/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// ============================================================
// @pixano/services — Storage, assets, compute, model runtime
// ============================================================

import type { Document } from "@pixano/document";

// --------------- Unsubscribe ---------------

export type Unsubscribe = () => void;

// --------------- Save Item (bridge to existing persistence) ---------------

export interface SaveItem {
  readonly change_type: "add" | "update" | "delete";
  readonly object: unknown;
}

// --------------- Storage Service ---------------

/**
 * Abstracts persistence — loading and saving dataset items.
 * Wraps existing API calls from @pixano/core.
 */
export interface StorageService {
  loadDocument(datasetId: string, itemId: string): Promise<Document>;
  saveChanges(datasetId: string, changes: readonly SaveItem[]): Promise<void>;
}

// --------------- Asset Manager ---------------

/**
 * Manages image/video asset loading with caching and preloading.
 * Replaces ad-hoc image loading throughout the codebase.
 */
export interface AssetManager {
  loadImage(uri: string): Promise<HTMLImageElement>;
  loadVideoFrame(viewName: string, frameIndex: number): Promise<HTMLImageElement>;
  preloadRange(viewName: string, startFrame: number, count: number): void;
  evict(uri: string): void;
  clearCache(): void;
  readonly cacheSize: number;
}

// --------------- Compute Job ---------------

export type ComputeJobStatus = "pending" | "running" | "completed" | "failed" | "cancelled";

/**
 * A handle to a running or completed compute job.
 * Supports progress tracking and cancellation.
 */
export interface ComputeJob<T = unknown> {
  readonly id: string;
  readonly status: ComputeJobStatus;
  readonly progress: number; // 0..1
  readonly result: Promise<T>;
  cancel(): void;
  onProgress(callback: (progress: number) => void): Unsubscribe;
}

// --------------- Cancellation Token ---------------

/** Cooperative cancellation token for long-running operations. */
export interface CancellationToken {
  readonly isCancelled: boolean;
  throwIfCancelled(): void;
  onCancel(callback: () => void): Unsubscribe;
}

// --------------- Compute Service ---------------

/**
 * Manages AI/compute job lifecycle.
 * Provides a job queue with progress reporting and cancellation.
 */
export interface ComputeService {
  submit<T>(job: ComputeJobDescriptor<T>): ComputeJob<T>;
  cancel(jobId: string): void;
  getJob(jobId: string): ComputeJob | undefined;
  getActiveJobs(): ReadonlyArray<ComputeJob>;
}

export interface ComputeJobDescriptor<T = unknown> {
  readonly id: string;
  readonly type: string;
  readonly run: (token: CancellationToken) => Promise<T>;
  readonly description?: string;
}

// --------------- Model Runtime ---------------

export type ModelRuntimeType = "local-onnx" | "remote-inference";

export interface ModelInput {
  readonly type: string;
  readonly data: unknown;
}

export interface ModelOutput {
  readonly type: string;
  readonly data: unknown;
}

/**
 * Abstraction over model execution backends.
 * Wraps ONNX runtime and remote pixano-inference API.
 */
export interface ModelRuntime {
  readonly id: string;
  readonly type: ModelRuntimeType;
  run(input: ModelInput): Promise<ModelOutput>;
  dispose(): void;
}
