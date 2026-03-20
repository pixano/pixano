/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { segmentImage } from "$lib/api/inferenceApi";
import { embeddings } from "$lib/stores/workspaceStores.svelte";
import type { Reference } from "$lib/types/dataset";
import type {
  ImageSegmentationTaskInput,
  ImageSegmentationTaskResult,
  NDArrayPayload,
} from "$lib/types/inference";
import type { SaveMaskShape } from "$lib/types/shapeTypes";
import type {
  EmbeddingValue,
  InteractiveSegmentationEmbeddingCache,
} from "$lib/types/workspace";

import { normalizeMaskToSaveShape } from "./maskNormalization";
import { toBoxPrompt } from "./promptSerialization";

export type InteractivePromptMode = "positive" | "negative" | "box";

export interface InteractivePromptPoint {
  x: number;
  y: number;
  label: 0 | 1;
}

export interface InteractivePromptBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface InteractivePromptState {
  points: InteractivePromptPoint[];
  box: InteractivePromptBox | null;
}

export interface InteractiveImageSource {
  width: number;
  height: number;
}

export interface InteractiveSegmentationPrediction {
  previewMask: SaveMaskShape;
  response: ImageSegmentationTaskResult;
  score: number | null;
}

interface InteractiveSegmentationSession {
  embeddingCache: InteractiveSegmentationEmbeddingCache | null;
  maskLogits: NDArrayPayload | null;
  previewMask: SaveMaskShape | null;
  latestRequestToken: number;
}

function isNDArrayPayload(value: EmbeddingValue | undefined): value is NDArrayPayload {
  return (
    value !== undefined &&
    value !== null &&
    typeof value === "object" &&
    "values" in value &&
    Array.isArray(value.values) &&
    "shape" in value &&
    Array.isArray(value.shape)
  );
}

function isEmbeddingCache(
  value: EmbeddingValue | undefined,
): value is InteractiveSegmentationEmbeddingCache {
  return (
    value !== undefined &&
    value !== null &&
    typeof value === "object" &&
    "image_embedding" in value &&
    isNDArrayPayload(value.image_embedding)
  );
}

function asCachedEmbedding(
  value: EmbeddingValue | undefined,
): InteractiveSegmentationEmbeddingCache | null {
  if (isEmbeddingCache(value)) {
    return value;
  }

  if (isNDArrayPayload(value)) {
    return { image_embedding: value };
  }

  if (
    value &&
    typeof value === "object" &&
    "dims" in value &&
    Array.isArray(value.dims) &&
    "data" in value &&
    value.data &&
    typeof value.data === "object" &&
    "length" in value.data
  ) {
    return {
      image_embedding: {
        values: Array.from(value.data as ArrayLike<number>),
        shape: value.dims as number[],
      },
    };
  }

  return null;
}

function hasReusableEmbedding(
  cache: InteractiveSegmentationEmbeddingCache | null,
): cache is InteractiveSegmentationEmbeddingCache & {
  high_resolution_features: NDArrayPayload[];
} {
  return Array.isArray(cache?.high_resolution_features) && cache.high_resolution_features.length > 0;
}

function buildSegmentationRequest(
  model: string,
  providerName: string,
  datasetId: string,
  viewId: string,
  prompt: InteractivePromptState,
  cachedEmbedding: InteractiveSegmentationEmbeddingCache | null,
  maskInput: NDArrayPayload | null,
): ImageSegmentationTaskInput {
  const points = prompt.points.length
    ? [prompt.points.map((point) => [Math.round(point.x), Math.round(point.y)])]
    : null;
  const labels = prompt.points.length ? [prompt.points.map((point) => point.label)] : null;
  // A box prompt is useful for seeding the first mask, but once we have
  // low-resolution mask logits and the user starts refining with point prompts,
  // re-sending the original box over-constrains SAM2 and can collapse the mask.
  // Keep the box in UI state, but refine from the current mask logits + points.
  const shouldSendBox = !(prompt.box && prompt.points.length > 0 && maskInput);
  const boxes = shouldSendBox ? toBoxPrompt(prompt.box) : null;
  const reusableEmbedding = hasReusableEmbedding(cachedEmbedding) ? cachedEmbedding : null;

  return {
    model,
    provider_name: providerName,
    dataset_id: datasetId,
    view_id: viewId,
    image_embedding: reusableEmbedding?.image_embedding ?? null,
    high_resolution_features: reusableEmbedding?.high_resolution_features ?? null,
    mask_input: maskInput,
    reset_predictor: true,
    points,
    labels,
    boxes,
    num_multimask_outputs: 1,
    multimask_output: false,
    return_image_embedding: reusableEmbedding === null,
    return_logits: true,
  };
}

export class InteractiveSegmenter {
  private readonly sessions = new Map<string, InteractiveSegmentationSession>();

  private getSession(viewId: string): InteractiveSegmentationSession {
    const existing = this.sessions.get(viewId);
    if (existing) {
      return existing;
    }

    const session: InteractiveSegmentationSession = {
      embeddingCache: null,
      maskLogits: null,
      previewMask: null,
      latestRequestToken: 0,
    };
    this.sessions.set(viewId, session);
    return session;
  }

  private syncStoredEmbedding(viewId: string): InteractiveSegmentationEmbeddingCache | null {
    const stored = asCachedEmbedding(embeddings.value[viewId]);
    const session = this.getSession(viewId);
    if (stored) {
      session.embeddingCache = stored;
      return stored;
    }

    return session.embeddingCache;
  }

  private persistEmbedding(viewId: string, cacheEntry: InteractiveSegmentationEmbeddingCache): void {
    const session = this.getSession(viewId);
    session.embeddingCache = cacheEntry;
    embeddings.update((current) => ({
      ...current,
      [viewId]: cacheEntry,
    }));
  }

  async ensureEmbedding(
    viewRef: Reference,
    datasetId: string,
    model: string,
    providerName: string,
  ): Promise<InteractiveSegmentationEmbeddingCache | null> {
    const existing = this.syncStoredEmbedding(viewRef.id);
    if (hasReusableEmbedding(existing)) {
      return existing;
    }

    const response = await segmentImage({
      model,
      provider_name: providerName,
      dataset_id: datasetId,
      view_id: viewRef.id,
      reset_predictor: true,
      return_image_embedding: true,
      return_logits: false,
      num_multimask_outputs: 1,
      multimask_output: false,
    });

    if (!response?.data.image_embedding || !response.data.high_resolution_features) {
      return null;
    }

    const cacheEntry: InteractiveSegmentationEmbeddingCache = {
      image_embedding: response.data.image_embedding,
      high_resolution_features: response.data.high_resolution_features,
    };
    this.persistEmbedding(viewRef.id, cacheEntry);
    return cacheEntry;
  }

  async predictMask(args: {
    datasetId: string;
    viewRef: Reference;
    itemId: string;
    image: InteractiveImageSource;
    model: string;
    providerName: string;
    prompt: InteractivePromptState;
  }): Promise<InteractiveSegmentationPrediction | null> {
    const cachedEmbedding =
      this.syncStoredEmbedding(args.viewRef.id);
    const session = this.getSession(args.viewRef.id);
    const requestToken = session.latestRequestToken + 1;
    session.latestRequestToken = requestToken;
    const response = await segmentImage(
      buildSegmentationRequest(
        args.model,
        args.providerName,
        args.datasetId,
        args.viewRef.id,
        args.prompt,
        cachedEmbedding,
        session.maskLogits,
      ),
    );

    if (!response) {
      return null;
    }

    const currentSession = this.sessions.get(args.viewRef.id);
    if (!currentSession || currentSession.latestRequestToken !== requestToken) {
      return null;
    }

    if (response.data.image_embedding && response.data.high_resolution_features) {
      const cacheEntry: InteractiveSegmentationEmbeddingCache = {
        image_embedding: response.data.image_embedding,
        high_resolution_features: response.data.high_resolution_features,
      };
      this.persistEmbedding(args.viewRef.id, cacheEntry);
    }

    const firstMask = response.data.masks[0]?.[0];
    if (!firstMask) {
      currentSession.maskLogits = response.data.mask_logits ?? null;
      currentSession.previewMask = null;
      return null;
    }

    const score = response.data.scores.values[0] ?? null;
    const previewMask = normalizeMaskToSaveShape({
      mask: firstMask,
      viewRef: args.viewRef,
      itemId: args.itemId,
      imageWidth: args.image.width,
      imageHeight: args.image.height,
    });
    currentSession.maskLogits = response.data.mask_logits ?? null;
    currentSession.previewMask = previewMask;

    return {
      previewMask,
      response,
      score,
    };
  }

  clear(viewRef?: Reference): void {
    if (viewRef) {
      this.sessions.delete(viewRef.id);
      if (isEmbeddingCache(embeddings.value[viewRef.id])) {
        embeddings.update((current) => {
          const next = { ...current };
          delete next[viewRef.id];
          return next;
        });
      }
      return;
    }

    const cachedViewIds = Object.entries(embeddings.value)
      .filter(([, value]) => isEmbeddingCache(value))
      .map(([viewId]) => viewId);
    this.sessions.clear();
    if (cachedViewIds.length > 0) {
      embeddings.update((current) => {
        const next = { ...current };
        for (const viewId of cachedViewIds) {
          delete next[viewId];
        }
        return next;
      });
    }
  }
}
