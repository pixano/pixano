/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { Conversation, Message } from "../dataset"

export enum MultimodalImageNLPTask {
  //Multimodal tasks
  CAPTIONING = "image_captioning",
  CONDITIONAL_GENERATION = "image_text_conditional_generation",
  EMBEDDING = "image_text_embedding",
  MATCHING = "image_text_matching",
  QUESTION_ANSWERING = "image_question_answering"
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
  task: string;
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
