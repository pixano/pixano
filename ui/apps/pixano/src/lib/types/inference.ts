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
  //Multimodal tasks
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

export interface InferenceModel {
  name: string;
  task: Task;
  provider_name?: string;
}

export interface InferenceServerState {
  connected: boolean;
  providers: ConnectedProvider[];
  defaultProvider: string | null;
  models: InferenceModel[];
  isLoading: boolean;
}

export interface SystemPrompt {
  content: string;
  question_type: QuestionTypeEnum;
  as_system: boolean;
}

interface ModelConfigConfig {
  name: string;
  task: string;
  path: string;
  config: object;
  processor_config: object;
}

export interface ModelConfig {
  config: ModelConfigConfig;
  provider: string;
}

export interface CondititionalGenerationTextImageInput {
  model: string;
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
