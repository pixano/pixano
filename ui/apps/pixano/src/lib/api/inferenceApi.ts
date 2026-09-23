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
    const response = await fetch("/inference/connected", {
      headers: { Accept: "application/json" },
      method: "GET",
    });

    if (!response.ok) {
      console.error("api.getInferenceServers -", response.status, response.statusText);
      return EMPTY_REGISTRY;
    }

    // The /connected payload keys providers by name; flatten to the array shape the app uses.
    const payload = (await response.json()) as {
      connected: boolean;
      providers: Record<string, { url: string | null }>;
      default_provider: string | null;
    };
    return {
      connected: payload.connected,
      providers: Object.entries(payload.providers ?? {}).map(([name, info]) => ({
        name,
        url: info?.url ?? null,
      })),
      default_provider: payload.default_provider,
    };
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
    const params = new URLSearchParams({ provider_type: type });
    if (url?.trim()) params.set("url", url.trim());
    if (apiKey?.trim()) params.set("api_key", apiKey.trim());

    const response = await fetch(`/inference/connect?${params.toString()}`, {
      headers: JSON_HEADERS,
      method: "POST",
    });

    if (!response.ok) {
      let detail = `${response.status} ${response.statusText}`;
      try {
        const body = (await response.json()) as { detail?: string };
        if (body.detail) detail = body.detail;
      } catch {
        // Response body not JSON — use status text
      }
      console.error("api.registerInferenceServer -", detail);
      return { error: detail };
    }

    const payload = (await response.json()) as {
      status: string;
      provider: string;
      url: string | null;
    };
    return { provider: { name: payload.provider, url: payload.url } };
  } catch (e) {
    console.error("api.registerInferenceServer -", e);
    return { error: String(e) };
  }
}

export async function listInferenceModels(): Promise<InferenceModel[]> {
  try {
    const response = await fetch("/inference/models/list", {
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
    "/inference/image_mask_generation",
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
    "/inference/video_mask_generation",
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
    "/inference/video_mask_generation/jobs",
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
    `/inference/video_mask_generation/jobs/${jobId}`,
    {
      headers: { Accept: "application/json" },
      method: "GET",
    },
    "getTrackingJob",
  );
}

export async function cancelTrackingJob(jobId: string): Promise<VideoTrackingJobStatus> {
  return requestJson<VideoTrackingJobStatus>(
    `/inference/video_mask_generation/jobs/${jobId}`,
    {
      headers: { Accept: "application/json" },
      method: "DELETE",
    },
    "cancelTrackingJob",
  );
}
