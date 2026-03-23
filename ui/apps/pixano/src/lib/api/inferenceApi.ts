/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { JSON_HEADERS, requestJson } from "./apiClient";
import type {
  CondititionalGenerationTextImageInput,
  ConnectedProvider,
  ImageSegmentationTaskInput,
  ImageSegmentationTaskResult,
  InferenceModel,
  InferenceProviderRegistry,
  VideoTrackingJobStatus,
  VideoTrackingTaskInput,
  VideoTrackingTaskResult,
  VLMResult,
} from "$lib/types/inference";

const EMPTY_REGISTRY: InferenceProviderRegistry = {
  connected: false,
  providers: [],
  default_provider: null,
};

const EMPTY_MODELS: InferenceModel[] = [];

export async function getInferenceServers(): Promise<InferenceProviderRegistry> {
  try {
    const response = await fetch("/app/inference/servers/", {
      headers: { Accept: "application/json" },
      method: "GET",
    });

    if (!response.ok) {
      console.error("api.getInferenceServers -", response.status, response.statusText);
      return EMPTY_REGISTRY;
    }

    return (await response.json()) as InferenceProviderRegistry;
  } catch (e) {
    console.error("api.getInferenceServers -", e);
    return EMPTY_REGISTRY;
  }
}

export async function registerInferenceServer(
  url: string | null,
  type: string = "pixano-inference",
  apiKey: string | null = null,
): Promise<{ provider: ConnectedProvider } | { error: string }> {
  try {
    const response = await fetch("/app/inference/servers/", {
      headers: JSON_HEADERS,
      method: "POST",
      body: JSON.stringify({
        type,
        url: url?.trim() || null,
        api_key: apiKey?.trim() || null,
      }),
    });

    if (!response.ok) {
      let detail = `${response.status} ${response.statusText}`;
      try {
        const body = await response.json();
        if (body.detail) detail = body.detail;
      } catch {}
      console.error("api.registerInferenceServer -", detail);
      return { error: detail };
    }

    const payload = (await response.json()) as {
      provider: ConnectedProvider;
      default_provider: string | null;
    };
    return { provider: payload.provider };
  } catch (e) {
    console.error("api.registerInferenceServer -", e);
    return { error: String(e) };
  }
}

export async function listInferenceModels(): Promise<InferenceModel[]> {
  try {
    const response = await fetch("/app/inference/models/", {
      headers: { Accept: "application/json" },
      method: "GET",
    });

    if (!response.ok) {
      console.error("api.listInferenceModels -", response.status, response.statusText);
      return EMPTY_MODELS;
    }

    return (await response.json()) as InferenceModel[];
  } catch (e) {
    console.error("api.listInferenceModels -", e);
    return EMPTY_MODELS;
  }
}

export async function vlm(input: CondititionalGenerationTextImageInput): Promise<VLMResult | null> {
  try {
    const response = await fetch("/inference/vlm", {
      headers: JSON_HEADERS,
      method: "POST",
      body: JSON.stringify(input),
    });

    if (!response.ok) {
      console.error("api.vlm -", response.status, response.statusText);
      return null;
    }

    return (await response.json()) as VLMResult;
  } catch (e) {
    console.error("api.vlm -", e);
    return null;
  }
}

export async function segmentImage(
  input: ImageSegmentationTaskInput,
): Promise<ImageSegmentationTaskResult> {
  return requestJson<ImageSegmentationTaskResult>(
    "/inference/segmentation",
    {
      headers: JSON_HEADERS,
      method: "POST",
      body: JSON.stringify(input),
    },
    "segmentImage",
  );
}

export async function trackVideo(input: VideoTrackingTaskInput): Promise<VideoTrackingTaskResult> {
  return requestJson<VideoTrackingTaskResult>(
    "/inference/tracking",
    {
      headers: JSON_HEADERS,
      method: "POST",
      body: JSON.stringify(input),
    },
    "trackVideo",
  );
}

export async function submitTrackingJob(
  input: VideoTrackingTaskInput,
): Promise<VideoTrackingJobStatus> {
  return requestJson<VideoTrackingJobStatus>(
    "/inference/tracking/jobs",
    {
      headers: JSON_HEADERS,
      method: "POST",
      body: JSON.stringify(input),
    },
    "submitTrackingJob",
  );
}

export async function getTrackingJob(jobId: string): Promise<VideoTrackingJobStatus> {
  return requestJson<VideoTrackingJobStatus>(
    `/inference/tracking/jobs/${jobId}`,
    {
      headers: { Accept: "application/json" },
      method: "GET",
    },
    "getTrackingJob",
  );
}

export async function cancelTrackingJob(jobId: string): Promise<VideoTrackingJobStatus> {
  return requestJson<VideoTrackingJobStatus>(
    `/inference/tracking/jobs/${jobId}`,
    {
      headers: { Accept: "application/json" },
      method: "DELETE",
    },
    "cancelTrackingJob",
  );
}
