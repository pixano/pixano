/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { Entity, Message, QuestionTypeEnum } from "./dataset";

export enum MultimodalImageNLPTask {
  //Multimodal tasks
  CAPTIONING = "image_captioning",
  CONDITIONAL_GENERATION = "text_image_conditional_generation",
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
  MASK_GENERATION = "image_mask_generation",
  OBJECT_DETECTION = "object_detection",
  SEMANTIC_SEGMENTATION = "semantic_segmentation",
  UNIVERSAL_SEGMENTATION = "universal_segmentation",
  ZERO_SHOT_CLASSIFICATION = "image_zero_shot_classification",
  ZERO_SHOT_DETECTION = "image_zero_shot_detection",
}

export enum VideoTask {
  MASK_GENERATION = "video_mask_generation",
}

export type Task = MultimodalImageNLPTask | ImageTask | VideoTask;

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
  dataset_id: string;
  conversation: Omit<Entity, "ui">;
  messages: Omit<Message, "ui">[];
  model: string;
  max_new_tokens?: number;
  temperature?: number;
  role_system?: string;
  role_user?: string;
  role_assistant?: string;
}
