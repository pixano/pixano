/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { Conversation, Message, QuestionTypeEnum } from "../dataset";

export enum MultimodalImageNLPTask {
  //Multimodal tasks
  CAPTIONING = "image_captioning",
  CONDITIONAL_GENERATION = "text_image_conditional_generation",
  EMBEDDING = "image_text_embedding",
  MATCHING = "image_text_matching",
  QUESTION_ANSWERING = "image_question_answering",
}

export interface PixanoInferenceInfo {
  selected: boolean;
  name: string;
  task: MultimodalImageNLPTask;
  prompts: SystemPrompt[];
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

export interface ModelList {
  name: string;
  task: MultimodalImageNLPTask;
}

export interface CondititionalGenerationTextImageInput {
  dataset_id: string;
  conversation: Conversation;
  messages: Message[];
  model: string;
  max_new_tokens?: number;
  temperature?: number;
  image_regex?: string;
  role_system?: string;
  role_user?: string;
  role_assistant?: string;
}
