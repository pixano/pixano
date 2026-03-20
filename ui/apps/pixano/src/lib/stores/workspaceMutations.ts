/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { completionModelsStore } from "./vqaStores.svelte";
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

function getMessageEntityIds(message: Message): string[] {
  if (Array.isArray(message.data.entity_ids)) {
    return message.data.entity_ids as string[];
  }
  if (typeof message.data.entity_id === "string" && message.data.entity_id !== "") {
    return [message.data.entity_id];
  }
  return [];
}

function buildPrompt(
  instruction: string,
  userContent: string,
  asSystem: boolean,
): CondititionalGenerationTextImageInput["prompt"] {
  if (instruction.trim() === "") {
    return userContent;
  }

  if (asSystem) {
    return [
      { role: "system", content: instruction },
      { role: "user", content: userContent },
    ];
  }

  return [{ role: "user", content: `${instruction}\n\n${userContent}`.trim() }];
}

function getNextMessageNumber(conversationId: string): number {
  const conversationMessages = messagesStore.value.filter(
    (message) => (message.data.conversation_id as string) === conversationId,
  );
  return conversationMessages.length === 0
    ? 0
    : Math.max(...conversationMessages.map((message) => message.data.number ?? 0)) + 1;
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

function getQuestionContext(question: Message, imageUrl: string): VqaMessageContext {
  return {
    recordId: (question.data.record_id as string) ?? question.data.item_id ?? "",
    viewId: (question.data.view_id as string) ?? "",
    conversationId: (question.data.conversation_id as string) ?? "",
    entityIds: getMessageEntityIds(question),
    imageUrl,
  };
}

// ─── generateAnswer ─────────────────────────────────────────────────────────────

export const generateAnswer = async (
  completionModel: InferenceModelSelection,
  question: Message,
  imageUrl: string,
) => {
  const questionData = question.data;
  const selectedCompletionModel =
    completionModelsStore.value.find((m) => isSameInferenceModel(m, completionModel)) ??
    completionModelsStore.value.find((m) => m.selected);
  const temperature = selectedCompletionModel?.temperature ?? 1.0;

  if (!isQuestionData(questionData)) {
    console.error("ERROR: Message is not a question");
    return;
  }

  if (question.data.question_type !== QuestionTypeEnum.OPEN) {
    console.warn("Sorry, generation is only available for Open questions for now.");
    return;
  }

  const context = getQuestionContext(question, imageUrl);
  const questionType = question.data.question_type ?? QuestionTypeEnum.OPEN;
  const promptInstruction =
    selectedCompletionModel?.prompts[MessageTypeEnum.ANSWER][questionType] ?? "";
  const input: CondititionalGenerationTextImageInput = {
    model: completionModel.name,
    provider_name: completionModel.provider_name,
    prompt: buildPrompt(
      promptInstruction,
      question.data.content,
      selectedCompletionModel?.prompts.as_system ?? false,
    ),
    images: imageUrl ? [imageUrl] : null,
    temperature,
  };

  try {
    const generatedAnswer = await api.vlm(input);

    if (!generatedAnswer) {
      console.error(
        "Model generation error: Unexpected error, please look at Pixano-Inference logs for more information.",
      );
      return null;
    }

    const newAnswer = createMessage({
      number: getNextMessageNumber(context.conversationId),
      record_id: context.recordId,
      view_id: context.viewId,
      conversation_id: context.conversationId,
      entity_ids: context.entityIds,
      type: MessageTypeEnum.ANSWER,
      user: "user",
      inference_metadata: generatedAnswer.metadata ?? {},
      content: generatedAnswer.data.generated_text,
      choices: [],
      source_type: question.data.source_type ?? undefined,
      source_name: question.data.source_name ?? undefined,
      source_metadata: question.data.source_metadata ?? undefined,
    });

    annotations.update((prevAnnotations) => [...prevAnnotations, newAnswer]);

    saveTo("add", newAnswer);

    return newAnswer;
  } catch {
    return null;
  }
};

// ─── generateQuestion ───────────────────────────────────────────────────────────

export const generateQuestion = async (
  completionModel: InferenceModelSelection,
  context: VqaMessageContext,
): Promise<{ content: string; choices: string[]; question_type: QuestionTypeEnum } | null> => {
  const selectedCompletionModel =
    completionModelsStore.value.find((m) => isSameInferenceModel(m, completionModel)) ??
    completionModelsStore.value.find((m) => m.selected);
  const temperature = selectedCompletionModel?.temperature ?? 1.0;
  const questionType =
    (Object.entries(selectedCompletionModel?.prompts[MessageTypeEnum.QUESTION] ?? {}).find(
      ([, value]) => value.trim() !== "",
    )?.[0] as QuestionTypeEnum | undefined) ?? QuestionTypeEnum.OPEN;
  const promptInstruction =
    selectedCompletionModel?.prompts[MessageTypeEnum.QUESTION][questionType] ?? "";

  const input: CondititionalGenerationTextImageInput = {
    model: completionModel.name,
    provider_name: completionModel.provider_name,
    prompt: buildPrompt(
      promptInstruction,
      "Generate one question for this image.",
      selectedCompletionModel?.prompts.as_system ?? false,
    ),
    images: context.imageUrl ? [context.imageUrl] : null,
    temperature,
  };

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
