/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { completionModelsStore, lastVlmPromptStore } from "./vqaStores.svelte";
import { annotations } from "./workspaceBaseStores.svelte";
import { messages as messagesStore } from "./workspaceStores.svelte";
import * as api from "$lib/api";
import {
  BaseSchema,
  isQuestionData,
  Message,
  MessageTypeEnum,
  QuestionTypeEnum,
} from "$lib/types/dataset";
import {
  isSameInferenceModel,
  type CondititionalGenerationTextImageInput,
  type InferenceModelSelection,
} from "$lib/types/inference";
import type {
  DeleteQuestionEvent,
  NewAnswerEvent,
  StoreQuestionEvent,
  UpdatedMessageEvent,
  VqaMessageContext,
} from "$lib/types/vqa";
import { createMessage, updateMessage } from "$lib/utils/messageUtils";
import { saveTo } from "$lib/utils/saveItemUtils";
import { buildQuestionThreads } from "$lib/utils/vqaThreads";

// ─── Helpers ────────────────────────────────────────────────────────────────────

function getMessageEntityIds(message: Message): string[] {
  if (Array.isArray(message.data.entity_ids)) {
    return message.data.entity_ids as string[];
  }
  if (typeof message.data.entity_id === "string" && message.data.entity_id !== "") {
    return [message.data.entity_id];
  }
  return [];
}

function getNextMessageNumber(conversationId: string): number {
  const conversationMessages = messagesStore.value.filter(
    (message) => (message.data.conversation_id as string) === conversationId,
  );
  return conversationMessages.length === 0
    ? 0
    : Math.max(...conversationMessages.map((message) => message.data.number ?? 0)) + 1;
}

function getQuestionContext(
  question: Message,
  datasetId: string,
  imageIds: string[],
): VqaMessageContext {
  return {
    recordId: (question.data.record_id as string) ?? question.data.item_id ?? "",
    viewId: (question.data.view_id as string) ?? "",
    conversationId: (question.data.conversation_id as string) ?? "",
    entityIds: getMessageEntityIds(question),
    datasetId,
    imageIds,
  };
}

// ─── Record History ─────────────────────────────────────────────────────────────

/**
 * Format all Q&A messages for a record as a structured context string.
 * Groups questions with their answers as `- Q: ... | A: ...` pairs.
 */
function formatRecordHistory(recordId: string, excludeMessageId?: string): string {
  const msgs = messagesStore.value
    .filter((m) => {
      const rid = (m.data.record_id as string) || m.data.item_id || "";
      return rid === recordId && m.id !== excludeMessageId;
    })
    .sort((a, b) => (a.data.number ?? 0) - (b.data.number ?? 0));

  if (msgs.length === 0) return "";

  const lines: string[] = [];
  let currentQ = "";
  for (const m of msgs) {
    if (m.data.type === MessageTypeEnum.QUESTION) {
      if (currentQ) lines.push(`- Q: ${currentQ}`);
      currentQ = String(m.data.content ?? "");
    } else {
      const answer = String(m.data.content ?? "");
      if (currentQ) {
        lines.push(`- Q: ${currentQ} | A: ${answer}`);
        currentQ = "";
      }
    }
  }
  if (currentQ) lines.push(`- Q: ${currentQ}`);

  return lines.join("\n");
}

// ─── Task Templates ─────────────────────────────────────────────────────────────

const NO_REPETITION_RULE =
  "NO REPETITION: Do not ask anything conceptually similar to questions in the Existing Q&A Context.";
const VISUAL_GROUNDING_RULE =
  "VISUAL GROUNDING: The question must be answerable ONLY by analyzing the image.";

export function questionTaskBody(questionType: QuestionTypeEnum, hasHistory: boolean): string {
  const rules: string[] = [];
  if (hasHistory) rules.push(NO_REPETITION_RULE);
  rules.push(VISUAL_GROUNDING_RULE);

  switch (questionType) {
    case QuestionTypeEnum.SINGLE_CHOICE:
    case QuestionTypeEnum.SINGLE_CHOICE_EXPLANATION:
      rules.push(
        "The answer must be definitively 'Yes' or 'No' based on the image.",
        "OUTPUT FORMAT: Output ONLY the raw text of your new question. No prefixes, quotes, or conversational text.",
      );
      return `Generate ONE NEW yes/no question about the visual content of this image.\n\n### Rules:\n${rules.map((r, i) => `${i + 1}. ${r}`).join("\n")}`;

    case QuestionTypeEnum.MULTI_CHOICE:
    case QuestionTypeEnum.MULTI_CHOICE_EXPLANATION:
      rules.push(
        "Exactly one option must be correct. The others should be plausible distractors.",
        "OUTPUT FORMAT:\nQuestion text\nA. first option\nB. second option\nC. third option\nD. fourth option",
      );
      return `Generate ONE NEW multiple-choice question about the visual content of this image with exactly 4 options.\n\n### Rules:\n${rules.map((r, i) => `${i + 1}. ${r}`).join("\n")}`;

    default:
      rules.push(
        "HIGH DIFFICULTY: Ask about spatial relationships, actions, fine-grained details, text in the image, or counting. Avoid trivial object identification.",
        "OUTPUT FORMAT: Output ONLY the raw text of your new question. No prefixes, quotes, or conversational text.",
      );
      return `Generate ONE NEW open-ended question about the visual content of this image.\n\n### Rules:\n${rules.map((r, i) => `${i + 1}. ${r}`).join("\n")}`;
  }
}

export function answerTaskBody(
  questionType: QuestionTypeEnum,
  questionContent: string,
  choices: string[],
): string {
  const formattedChoices =
    choices.length > 0
      ? choices.map((c, i) => `${String.fromCharCode(65 + i)}. ${c}`).join("\n")
      : "";

  switch (questionType) {
    case QuestionTypeEnum.SINGLE_CHOICE:
      return `Answer the following yes/no question about this image.\n\n### Question:\n${questionContent}\n\n### Rules:\n1. Reply with exactly 'Yes' or 'No'.\n2. Base your answer ONLY on what you see in the image.`;

    case QuestionTypeEnum.SINGLE_CHOICE_EXPLANATION:
      return `Answer the following yes/no question about this image.\n\n### Question:\n${questionContent}\n\n### Rules:\n1. Reply with 'Yes' or 'No' followed by a brief explanation.\n2. Base your answer ONLY on what you see in the image.`;

    case QuestionTypeEnum.MULTI_CHOICE:
      return `Answer the following multiple-choice question about this image.\n\n### Question:\n${questionContent}\n\n### Choices:\n${formattedChoices}\n\n### Rules:\n1. Reply with ONLY the letter of the correct answer (e.g. 'A').\n2. Base your answer ONLY on what you see in the image.`;

    case QuestionTypeEnum.MULTI_CHOICE_EXPLANATION:
      return `Answer the following multiple-choice question about this image.\n\n### Question:\n${questionContent}\n\n### Choices:\n${formattedChoices}\n\n### Rules:\n1. Reply with the letter of the correct answer followed by a brief explanation.\n2. Base your answer ONLY on what you see in the image.`;

    default:
      return `Answer the following question about this image concisely and accurately.\n\n### Question:\n${questionContent}\n\n### Rules:\n1. Base your answer ONLY on what you see in the image.\n2. Be concise but complete.\n3. OUTPUT FORMAT: Output ONLY the answer text. No prefixes or conversational text.`;
  }
}

// ─── Prompt Builder ─────────────────────────────────────────────────────────────

interface PromptOptions {
  systemInstruction: string;
  taskBody: string;
  historyContext: string;
}

/**
 * Build a structured prompt for the VLM API.
 *
 * Always produces exactly 2 messages:
 * - system: the editable system instruction (expert role)
 * - user: optional history context section + task body with rules
 *
 * History is NEVER injected as separate chat messages — it's formatted
 * as a `### Existing Q&A Context` section inside the user message.
 */
function buildPrompt(opts: PromptOptions): CondititionalGenerationTextImageInput["prompt"] {
  const { systemInstruction, taskBody, historyContext } = opts;

  const sections: string[] = [];

  if (historyContext) {
    sections.push(`### Existing Q&A Context:\n${historyContext}`);
  }

  sections.push(`### Task:\n${taskBody}`);

  const userContent = sections.join("\n\n");

  if (!systemInstruction.trim()) {
    return userContent;
  }

  return [
    { role: "system", content: systemInstruction },
    { role: "user", content: userContent },
  ];
}

function logVlmInput(input: CondititionalGenerationTextImageInput): void {
  lastVlmPromptStore.value = {
    prompt: input.prompt,
    model: input.model,
    provider: input.provider_name ?? "",
    temperature: input.temperature ?? 0.7,
    imageCount: input.image_ids?.length ?? 0,
    timestamp: Date.now(),
  };
}

// ─── addAnswer ──────────────────────────────────────────────────────────────────

export const addAnswer = (detail: NewAnswerEvent) => {
  const { questionId, content } = detail;

  const messages = messagesStore.value;
  const question = messages.find(
    (message) => message.data.type === MessageTypeEnum.QUESTION && message.id === questionId,
  );

  if (!question) {
    return;
  }

  const newAnswer = createMessage({
    number: getNextMessageNumber((question.data.conversation_id as string) ?? ""),
    record_id: (question.data.record_id as string) ?? question.data.item_id ?? "",
    view_id: (question.data.view_id as string) ?? "",
    conversation_id: (question.data.conversation_id as string) ?? "",
    entity_ids: getMessageEntityIds(question),
    item_id: question.data.item_id ?? "",
    view_name: question.data.view_name ?? "",
    entity_id: question.data.entity_id ?? "",
    source_type: question.data.source_type ?? undefined,
    source_name: question.data.source_name ?? undefined,
    source_metadata: question.data.source_metadata ?? undefined,
    type: MessageTypeEnum.ANSWER,
    user: "user",
    inference_metadata: {},
    content,
    choices: [],
  });

  annotations.update((prevAnnotations) => [...prevAnnotations, newAnswer]);

  saveTo("add", newAnswer);
};

// ─── addQuestion ────────────────────────────────────────────────────────────────

export const addQuestion = ({
  newQuestionData,
  context,
}: {
  newQuestionData: StoreQuestionEvent;
  context: VqaMessageContext;
}) => {
  const { labelFormat, ...questionData } = newQuestionData;

  const newQuestion = createMessage({
    ...questionData,
    number: 0,
    record_id: context.recordId,
    view_id: context.viewId,
    conversation_id: context.conversationId,
    entity_ids: context.entityIds,
    item_id: context.recordId,
    view_name: "",
    entity_id: context.entityIds[0] ?? "",
    type: MessageTypeEnum.QUESTION,
    user: "user",
    inference_metadata: {},
  });

  if (labelFormat) {
    (newQuestion.ui as Record<string, unknown>).labelFormat = labelFormat;
  }

  annotations.update((prevAnnotations) => [...prevAnnotations, newQuestion]);

  saveTo("add", newQuestion);
};

// ─── deleteQuestion ─────────────────────────────────────────────────────────────

export const deleteQuestion = ({ questionId }: DeleteQuestionEvent) => {
  const allAnnotations = annotations.value;

  const messages = allAnnotations.filter((a): a is Message => a instanceof Message);
  const questionThread = buildQuestionThreads(messages).find(
    (thread) => thread.question.id === questionId,
  );
  const question = questionThread?.question;

  if (!question) {
    console.error("ERROR: Question not found for deletion", questionId);
    return;
  }

  const messagesToDelete = questionThread?.messages ?? [question];

  const idsToDelete = new Set(messagesToDelete.map((m) => m.id));

  annotations.update((prev) => prev.filter((a) => !idsToDelete.has(a.id)));

  for (const message of messagesToDelete) {
    saveTo("delete", message);
  }
};

// ─── generateAnswer ─────────────────────────────────────────────────────────────

export const generateAnswer = async (
  completionModel: InferenceModelSelection,
  question: Message,
  datasetId: string,
  imageIds: string[],
): Promise<string | null> => {
  const questionData = question.data;
  const selectedCompletionModel =
    completionModelsStore.value.find((m) => isSameInferenceModel(m, completionModel)) ??
    completionModelsStore.value.find((m) => m.selected);
  const temperature = selectedCompletionModel?.temperature ?? 0.7;

  if (!isQuestionData(questionData)) {
    console.error("ERROR: Message is not a question");
    return null;
  }

  const context = getQuestionContext(question, datasetId, imageIds);
  const questionType = (question.data.question_type as QuestionTypeEnum) ?? QuestionTypeEnum.OPEN;
  const systemInstruction =
    selectedCompletionModel?.prompts[MessageTypeEnum.ANSWER][questionType] ?? "";
  const includeHist = selectedCompletionModel?.includeHistory ?? false;

  const questionContent = String(question.data.content ?? "");
  const choices = (question.data.choices as string[]) ?? [];

  const historyContext = includeHist ? formatRecordHistory(context.recordId, question.id) : "";

  const input: CondititionalGenerationTextImageInput = {
    model: completionModel.name,
    provider_name: completionModel.provider_name,
    prompt: buildPrompt({
      systemInstruction,
      taskBody: answerTaskBody(questionType, questionContent, choices),
      historyContext,
    }),
    dataset_id: datasetId || null,
    image_ids: imageIds.length > 0 ? imageIds : null,
    temperature,
  };

  logVlmInput(input);

  try {
    const result = await api.vlm(input);
    if (!result) {
      console.error("Model generation error: VLM returned no result.");
      return null;
    }
    return result.data.generated_text;
  } catch (err) {
    console.error("Model generation error:", err);
    return null;
  }
};

// ─── generateQuestion ───────────────────────────────────────────────────────────

export const generateQuestion = async (
  completionModel: InferenceModelSelection,
  context: VqaMessageContext,
  questionType: QuestionTypeEnum = QuestionTypeEnum.OPEN,
): Promise<{ content: string; choices: string[]; question_type: QuestionTypeEnum } | null> => {
  const selectedCompletionModel =
    completionModelsStore.value.find((m) => isSameInferenceModel(m, completionModel)) ??
    completionModelsStore.value.find((m) => m.selected);
  const temperature = selectedCompletionModel?.temperature ?? 0.7;
  const systemInstruction =
    selectedCompletionModel?.prompts[MessageTypeEnum.QUESTION][questionType] ?? "";
  const includeHist = selectedCompletionModel?.includeHistory ?? false;

  const historyContext = includeHist ? formatRecordHistory(context.recordId) : "";

  const input: CondititionalGenerationTextImageInput = {
    model: completionModel.name,
    provider_name: completionModel.provider_name,
    prompt: buildPrompt({
      systemInstruction,
      taskBody: questionTaskBody(questionType, historyContext.length > 0),
      historyContext,
    }),
    dataset_id: context.datasetId || null,
    image_ids: context.imageIds.length > 0 ? context.imageIds : null,
    temperature,
  };

  logVlmInput(input);

  try {
    const generatedQuestion = await api.vlm(input);

    if (!generatedQuestion) {
      return null;
    }

    return {
      content: generatedQuestion.data.generated_text,
      choices: [],
      question_type: questionType,
    };
  } catch (err) {
    console.error("Model generation error:", err);
    return null;
  }
};

// ─── updateMessageContent ───────────────────────────────────────────────────────

export const updateMessageContent = (detail: UpdatedMessageEvent) => {
  const { messageId, content } = detail;

  const messages = messagesStore.value;
  const previousMessage = messages.find((message) => message.id === messageId);

  if (!previousMessage) {
    return;
  }

  const updatedMessage = updateMessage({ prevMessage: previousMessage, content });

  annotations.update((prevAnnotations) =>
    prevAnnotations.map((annotation) =>
      annotation.is_type(BaseSchema.Message) && annotation.id === messageId
        ? updatedMessage
        : annotation,
    ),
  );

  saveTo("update", updatedMessage);
};
