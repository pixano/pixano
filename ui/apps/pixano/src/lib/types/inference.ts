/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { QuestionTypeEnum } from "./dataset";

export interface ConversationPromptContext {
  conversation_id: string;
  record_id: string;
  view_id: string;
  entity_ids: string[];
}

export enum MultimodalImageNLPTask {
  CAPTIONING = "image_captioning",
  VLM = "vlm",
  EMBEDDING = "image_text_embedding",
  MATCHING = "image_text_matching",
  QUESTION_ANSWERING = "image_question_answering",
}

export enum ImageTask {
  CLASSIFICATION = "image_classification",
  DEPTH_ESTIMATION = "depth_estimation",
  INSTANCE_SEGMENTATION = "instance_segmentation",
  FEATURE_EXTRACTION = "image_feature_extraction",
  KEYPOINT_DETECTION = "keypoint_detection",
  SEGMENTATION = "segmentation",
  OBJECT_DETECTION = "object_detection",
  SEMANTIC_SEGMENTATION = "semantic_segmentation",
  UNIVERSAL_SEGMENTATION = "universal_segmentation",
  ZERO_SHOT_CLASSIFICATION = "image_zero_shot_classification",
  DETECTION = "detection",
}

export enum VideoTask {
  TRACKING = "tracking",
}

export type Task = MultimodalImageNLPTask | ImageTask | VideoTask;

export interface ConnectedProvider {
  name: string;
  url: string | null;
}

export interface InferenceProviderRegistry {
  connected: boolean;
  providers: ConnectedProvider[];
  default_provider: string | null;
}

export interface InferenceModelSelection {
  name: string;
  provider_name: string;
}

export interface InferenceModel extends InferenceModelSelection {
  task: Task;
  model_path?: string | null;
  model_class?: string | null;
}

export type InferenceLoadStatus = "idle" | "loading" | "loaded" | "error";

export interface InferenceServerState {
  status: InferenceLoadStatus;
  connected: boolean;
  providers: ConnectedProvider[];
  defaultProvider: string | null;
  models: InferenceModel[];
}

export interface SystemPrompt {
  content: string;
  question_type: QuestionTypeEnum;
  as_system: boolean;
}

export interface CondititionalGenerationTextImageInput {
  model: string;
  provider_name?: string | null;
  prompt: string | Array<{ role: string; content: string }>;
  images?: string[] | null;
  max_new_tokens?: number;
  temperature?: number;
}

export interface VLMOutput {
  generated_text: string;
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  generation_config: Record<string, unknown>;
}

export interface VLMResult {
  data: VLMOutput;
  timestamp: string;
  processing_time: number;
  metadata: Record<string, unknown>;
  id: string;
  status: string;
}

export interface NDArrayPayload {
  values: number[];
  shape: number[];
}

export interface CompressedRLEPayload {
  size: [number, number] | number[];
  counts: string | number[];
}

export interface ImageSegmentationTaskInput {
  model: string;
  provider_name?: string | null;
  dataset_id: string;
  view_id: string;
  image_embedding?: NDArrayPayload | null;
  high_resolution_features?: NDArrayPayload[] | null;
  mask_input?: NDArrayPayload | null;
  reset_predictor?: boolean;
  points?: number[][][] | null;
  labels?: number[][] | null;
  boxes?: number[][] | null;
  num_multimask_outputs?: number;
  multimask_output?: boolean;
  return_image_embedding?: boolean;
  return_logits?: boolean;
}

export interface ImageSegmentationTaskOutput {
  masks: CompressedRLEPayload[][];
  scores: NDArrayPayload;
  image_embedding?: NDArrayPayload | null;
  high_resolution_features?: NDArrayPayload[] | null;
  mask_logits?: NDArrayPayload | null;
}

export interface ImageSegmentationTaskResult {
  data: ImageSegmentationTaskOutput;
  timestamp: string;
  processing_time: number;
  metadata: Record<string, unknown>;
  id: string;
  status: string;
}

export interface VideoTrackingTaskInput {
  model: string;
  provider_name?: string | null;
  dataset_id: string;
  record_id: string;
  view_name: string;
  start_frame_index: number;
  frame_count: number;
  objects_ids: number[];
  prompt_frame_indexes: number[];
  points?: number[][][] | null;
  labels?: number[][] | null;
  boxes?: number[][] | null;
  propagate?: boolean;
  interval?: {
    start_frame: number;
    end_frame: number;
    direction: "forward" | "backward";
  } | null;
  keyframes?: Array<{
    frame_index: number;
    points?: Array<{ x: number; y: number; label: 0 | 1 }> | null;
    box?: { x: number; y: number; width: number; height: number } | null;
    mask?: CompressedRLEPayload | null;
  }> | null;
}

export interface VideoTrackingTaskOutput {
  objects_ids: number[];
  frame_indexes: number[];
  masks: CompressedRLEPayload[];
}

export interface VideoTrackingTaskResult {
  data: VideoTrackingTaskOutput;
  timestamp: string;
  processing_time: number;
  metadata: Record<string, unknown>;
  id: string;
  status: string;
}

export type VideoTrackingJobState = "queued" | "running" | "completed" | "failed" | "canceled";

export interface VideoTrackingJobStatus {
  job_id: string;
  status: VideoTrackingJobState;
  detail?: string | null;
  data?: VideoTrackingTaskOutput | null;
}

export function getInferenceModelKey(model: InferenceModelSelection): string {
  return `${model.provider_name}::${model.name}`;
}

export function isSameInferenceModel(
  left: InferenceModelSelection | null | undefined,
  right: InferenceModelSelection | null | undefined,
): boolean {
  return (
    left !== null &&
    left !== undefined &&
    right !== null &&
    right !== undefined &&
    left.name === right.name &&
    left.provider_name === right.provider_name
  );
}

export function formatInferenceProviderName(providerName: string): string {
  return providerName.includes("@")
    ? providerName.substring(providerName.indexOf("@") + 1)
    : providerName;
}
