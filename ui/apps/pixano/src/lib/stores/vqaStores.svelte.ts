/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { reactiveStore } from "./reactiveStore.svelte";
import { MessageTypeEnum, QuestionTypeEnum } from "$lib/types/dataset";
import {
  getInferenceModelKey,
  type CondititionalGenerationTextImageInput,
  type InferenceModelSelection,
} from "$lib/types/inference";

// ─── Types ──────────────────────────────────────────────────────────────────────

export interface PixanoInferenceCompletionModel extends InferenceModelSelection {
  selected: boolean;
  prompts: MessageGenerationPrompts;
  temperature: number;
  includeHistory: boolean;
}

export type MessageGenerationPrompts = {
  [key in MessageTypeEnum]: PromptByQuestionType;
} & { as_system: boolean };

export type PromptByQuestionType = Record<QuestionTypeEnum, string>;

export interface VlmPromptDebugEntry {
  prompt: CondititionalGenerationTextImageInput["prompt"];
  model: string;
  provider: string;
  temperature: number;
  imageCount: number;
  timestamp: number;
}

// ─── Default Prompts ────────────────────────────────────────────────────────────

const DEFAULT_TEMPERATURE = 0.7;

const QUESTION_SYSTEM_PROMPT =
  "You are an expert visual data annotator tasked with generating high-quality questions for a Visual Question Answering (VQA) dataset. You must follow instructions precisely and output strictly the requested format.";

const ANSWER_SYSTEM_PROMPT =
  "You are an expert visual data annotator tasked with answering questions about images for a Visual Question Answering (VQA) dataset. You must follow instructions precisely and output strictly the requested format.";

const DEFAULT_QUESTION_PROMPTS: Record<QuestionTypeEnum, string> = {
  [QuestionTypeEnum.OPEN]: QUESTION_SYSTEM_PROMPT,
  [QuestionTypeEnum.SINGLE_CHOICE]: QUESTION_SYSTEM_PROMPT,
  [QuestionTypeEnum.SINGLE_CHOICE_EXPLANATION]: QUESTION_SYSTEM_PROMPT,
  [QuestionTypeEnum.MULTI_CHOICE]: QUESTION_SYSTEM_PROMPT,
  [QuestionTypeEnum.MULTI_CHOICE_EXPLANATION]: QUESTION_SYSTEM_PROMPT,
};

const DEFAULT_ANSWER_PROMPTS: Record<QuestionTypeEnum, string> = {
  [QuestionTypeEnum.OPEN]: ANSWER_SYSTEM_PROMPT,
  [QuestionTypeEnum.SINGLE_CHOICE]: ANSWER_SYSTEM_PROMPT,
  [QuestionTypeEnum.SINGLE_CHOICE_EXPLANATION]: ANSWER_SYSTEM_PROMPT,
  [QuestionTypeEnum.MULTI_CHOICE]: ANSWER_SYSTEM_PROMPT,
  [QuestionTypeEnum.MULTI_CHOICE_EXPLANATION]: ANSWER_SYSTEM_PROMPT,
};

// ─── Stores ─────────────────────────────────────────────────────────────────────

export const completionModelsStore = reactiveStore<PixanoInferenceCompletionModel[]>([]);
export const lastVlmPromptStore = reactiveStore<VlmPromptDebugEntry | null>(null);

// ─── Sync Logic ─────────────────────────────────────────────────────────────────

function buildDefaultPrompts(): MessageGenerationPrompts {
  const questionPrompts = Object.fromEntries(
    Object.values(QuestionTypeEnum).map((qt) => [qt, DEFAULT_QUESTION_PROMPTS[qt] ?? ""]),
  ) as PromptByQuestionType;

  const answerPrompts = Object.fromEntries(
    Object.values(QuestionTypeEnum).map((qt) => [qt, DEFAULT_ANSWER_PROMPTS[qt] ?? ""]),
  ) as PromptByQuestionType;

  return {
    ...Object.fromEntries(
      Object.values(MessageTypeEnum).map((key) => [key, answerPrompts]),
    ),
    [MessageTypeEnum.QUESTION]: questionPrompts,
    [MessageTypeEnum.ANSWER]: answerPrompts,
    as_system: true,
  } as MessageGenerationPrompts;
}

export function syncCompletionModels(availableModels: InferenceModelSelection[]): void {
  const current = completionModelsStore.value;
  const defaultPrompts = buildDefaultPrompts();

  const existingByKey = new Map(
    current.map((m) => [getInferenceModelKey(m), m]),
  );

  const next = availableModels.map(
    (model) =>
      existingByKey.get(getInferenceModelKey(model)) ?? {
        ...model,
        selected: false,
        prompts: defaultPrompts,
        temperature: DEFAULT_TEMPERATURE,
        includeHistory: false,
      },
  );

  const hasChange =
    next.length !== current.length || next.some((m, i) => m !== current[i]);

  if (hasChange) {
    completionModelsStore.value = next;
  }
}
