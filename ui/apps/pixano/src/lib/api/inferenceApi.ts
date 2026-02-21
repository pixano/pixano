/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Message } from "$lib/types/dataset";
import type {
  CondititionalGenerationTextImageInput,
  ConnectedProvider,
  ModelConfig,
  Task,
} from "$lib/types/inference";
import { createTypedAnnotation } from "$lib/utils/domainFactories";

import { apiFetch, apiMutate, JSON_HEADERS } from "./apiClient";

function buildModelsUrl(basePath: string, task: Task | null): string {
  if (task === null) {
    return basePath;
  }
  return `${basePath}?task=${encodeURIComponent(task)}`;
}

// ─── deleteModel ────────────────────────────────────────────────────────────────

export function deleteModel(modelName: string): Promise<void> {
  return apiMutate(
    `/inference/models/delete/${modelName}`,
    { headers: JSON_HEADERS, method: "DELETE" },
    "deleteModel",
  );
}

// ─── disconnectProvider ─────────────────────────────────────────────────────────

export async function disconnectProvider(providerName: string): Promise<boolean> {
  try {
    const response = await fetch(`/inference/disconnect/${encodeURIComponent(providerName)}`, {
      headers: JSON_HEADERS,
      method: "POST",
    });
    return response.ok;
  } catch {
    return false;
  }
}

// ─── conditional_generation_text_image ───────────────────────────────────────────

export async function conditional_generation_text_image(
  input: CondititionalGenerationTextImageInput,
): Promise<Message | null> {
  try {
    const response = await fetch("/inference/tasks/conditional_generation/text-image", {
      headers: JSON_HEADERS,
      method: "POST",
      body: JSON.stringify(input),
    });

    if (!response.ok) {
      return null;
    }
    return createTypedAnnotation(await response.json()) as Message;
  } catch (e) {
    console.error("api.conditional_generation_text_image -", e);
    return null;
  }
}

// ─── getInferenceStatus ─────────────────────────────────────────────────────────

export interface InferenceStatusResponse {
  connected: boolean;
  providers: ConnectedProvider[];
  default: string | null;
}

const DEFAULT_INFERENCE_STATUS: InferenceStatusResponse = {
  connected: false,
  providers: [],
  default: null,
};

export async function getInferenceStatus(): Promise<InferenceStatusResponse> {
  try {
    const response = await fetch("/inference/status", {
      headers: { Accept: "application/json" },
      method: "GET",
    });

    if (!response.ok) {
      return DEFAULT_INFERENCE_STATUS;
    }

    return (await response.json()) as InferenceStatusResponse;
  } catch {
    return DEFAULT_INFERENCE_STATUS;
  }
}

// ─── instantiateModel ───────────────────────────────────────────────────────────

export async function instantiateModel(modelConfig: ModelConfig): Promise<boolean> {
  try {
    const response = await fetch(`/inference/models/instantiate`, {
      headers: JSON_HEADERS,
      method: "POST",
      body: JSON.stringify(modelConfig),
    });

    if (!response.ok) {
      console.error("api.instantiateModel -", response.status, response.statusText);
      return false;
    }

    return true;
  } catch (e) {
    console.error("api.instantiateModel -", e);
    return false;
  }
}

// ─── isInferenceApiHealthy ──────────────────────────────────────────────────────

export async function isInferenceApiHealthy(url: string): Promise<boolean> {
  try {
    const response = await fetch(`/inference/connect?url=${encodeURIComponent(url)}`, {
      headers: JSON_HEADERS,
      method: "POST",
      signal: AbortSignal.timeout(4000),
    });
    return response.ok;
  } catch {
    return false;
  }
}

// ─── listAllModels ──────────────────────────────────────────────────────────────

export interface ModelWithProvider {
  name: string;
  task: Task;
  provider_name: string;
}

export function listAllModels(task: Task | null = null): Promise<ModelWithProvider[]> {
  const url = buildModelsUrl("/inference/models/list-all", task);

  return apiFetch(
    url,
    { headers: JSON_HEADERS, method: "GET" },
    [] as ModelWithProvider[],
    "listAllModels",
  );
}

// ─── listModels ─────────────────────────────────────────────────────────────────

interface Model {
  name: string;
  task: Task;
}

export function listModels(task: Task | null = null): Promise<Model[]> {
  const url = buildModelsUrl("/inference/models/list", task);

  return apiFetch(
    url,
    { headers: JSON_HEADERS, method: "GET" },
    [] as Model[],
    "listModels",
  );
}
