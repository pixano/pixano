/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import * as api from "$lib/api";
import {
  BaseSchema,
  isQuestionData,
  Message,
  MessageTypeEnum,
  QuestionTypeEnum,
} from "$lib/types/dataset";
import type { CondititionalGenerationTextImageInput } from "$lib/types/inference";
import type {
  DeleteQuestionEvent,
  NewAnswerEvent,
  StoreQuestionEvent,
  UpdatedMessageEvent,
} from "$lib/types/vqa";
import { Entity } from "$lib/types/dataset";

import { currentDatasetStore } from "./appStores.svelte";
import { vqaModels } from "./inferenceStores.svelte";
import { completionModelsStore } from "./vqaStores.svelte";
import { saveTo } from "$lib/utils/saveItemUtils";
import { removeFieldFromValue } from "$lib/utils/coreUtils";
import { createMessage, updateAnswerMessage } from "$lib/utils/messageUtils";
import {
  annotations,
  conversations,
  messages as messagesStore,
} from "./workspaceStores.svelte";

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
    number: question.data.number ?? 0,
    item_id: question.data.item_id ?? "",
    view_name: question.data.view_name ?? "",
    frame_id: question.data.frame_id ?? "",
    entity_id: question.data.entity_id ?? "",
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
  parentEntity,
}: {
  newQuestionData: StoreQuestionEvent;
  parentEntity: Entity;
}) => {
  const messages = messagesStore.value;

  const newQuestionNumber =
    messages.length === 0 ? 0 : Math.max(...messages.map((m) => m.data.number)) + 1;

  const { labelFormat, ...questionData } = newQuestionData;

  const newQuestion = createMessage({
    ...questionData,
    number: newQuestionNumber,
    entity_id: parentEntity.id,
    view_name: "",
    frame_id: "",
    item_id: parentEntity.data.item_id,
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

  const question = allAnnotations.find(
    (a) => a.id === questionId && a instanceof Message && a.data.type === MessageTypeEnum.QUESTION,
  ) as Message | undefined;

  if (!question) {
    console.error("ERROR: Question not found for deletion", questionId);
    return;
  }

  const questionNumber = question.data.number;

  const messagesToDelete = allAnnotations.filter(
    (a) => a instanceof Message && a.data.number === questionNumber,
  );

  const idsToDelete = new Set(messagesToDelete.map((m) => m.id));

  annotations.update((prev) => prev.filter((a) => !idsToDelete.has(a.id)));

  for (const message of messagesToDelete) {
    saveTo("delete", message);
  }
};

// ─── generateAnswer ─────────────────────────────────────────────────────────────

export const generateAnswer = async (completionModel: string, question: Message) => {
  const questionData = question.data;
  const temperature = completionModelsStore.value.find((m) => m.selected)?.temperature ?? 1.0;

  if (!isQuestionData(questionData)) {
    console.error("ERROR: Message is not a question");
    return;
  }

  if (question.data.question_type !== QuestionTypeEnum.OPEN) {
    console.warn("Sorry, generation is only available for Open questions for now.");
    return;
  }

  const [conversation] = conversations.value;

  if (conversation === undefined) {
    return null;
  }

  const selectedVqa = vqaModels.value.find((m) => m.name === completionModel);
  const input: CondititionalGenerationTextImageInput = {
    dataset_id: currentDatasetStore.value.id,
    conversation: removeFieldFromValue(conversation, "ui"),
    messages: [removeFieldFromValue(question, "ui")],
    model: completionModel,
    temperature,
    provider_name: selectedVqa?.provider_name,
  };

  try {
    const generatedAnswer = await api.conditional_generation_text_image(input);

    if (!generatedAnswer || !("data" in generatedAnswer)) {
      console.error(
        "Model generation error: Unexpected error, please look at Pixano-Inference logs for more information.",
      );
      return null;
    }

    annotations.update((prevAnnotations) => [...prevAnnotations, generatedAnswer]);

    saveTo("add", generatedAnswer);

    return generatedAnswer;
  } catch {
    return null;
  }
};

// ─── generateQuestion ───────────────────────────────────────────────────────────

export const generateQuestion = async (
  completionModel: string,
): Promise<{ content: string; choices: string[] } | null> => {
  const [conversation] = conversations.value;
  const prompt =
    completionModelsStore.value.find((m) => m.selected)?.prompts[MessageTypeEnum.QUESTION][
      QuestionTypeEnum.OPEN
    ] ?? "";
  const temperature = completionModelsStore.value.find((m) => m.selected)?.temperature ?? 1.0;

  if (conversation === undefined) {
    return null;
  }

  const lastMessageOfConversation = messagesStore.value.sort(
    (a, b) => b.data.number - a.data.number,
  )[0];

  const systemMessage = createMessage({
    item_id: conversation.data.item_id,
    view_name: "",
    frame_id: "",
    entity_id: conversation.id,
    type: MessageTypeEnum.QUESTION,
    question_type: QuestionTypeEnum.OPEN,
    user: "user",
    inference_metadata: {},
    choices: [],
    number: lastMessageOfConversation ? lastMessageOfConversation.data.number + 1 : 0,
    content: prompt,
  });

  const selectedVqa = vqaModels.value.find((m) => m.name === completionModel);
  const input: CondititionalGenerationTextImageInput = {
    dataset_id: currentDatasetStore.value.id,
    conversation: removeFieldFromValue(conversation, "ui"),
    messages: [removeFieldFromValue(systemMessage, "ui")],
    model: completionModel,
    temperature,
    provider_name: selectedVqa?.provider_name,
  };

  try {
    const generatedQuestion = await api.conditional_generation_text_image(input);

    if (!generatedQuestion) {
      return null;
    }

    return { content: generatedQuestion.data.content, choices: [] };
  } catch (err) {
    console.error("Model generation error:", err);
    return null;
  }
};

// ─── updateMessageContent ───────────────────────────────────────────────────────

export const updateMessageContent = (detail: UpdatedMessageEvent) => {
  const { answerId, content } = detail;

  const messages = messagesStore.value;
  const prevAnswer = messages.find(
    (message) => message.data.type === MessageTypeEnum.ANSWER && message.id === answerId,
  );

  if (!prevAnswer) {
    return;
  }

  const updatedMessage = updateAnswerMessage({ prevAnswer, content });

  annotations.update((prevAnnotations) =>
    prevAnnotations.map((annotation) =>
      annotation.is_type(BaseSchema.Message) && annotation.id === answerId
        ? updatedMessage
        : annotation,
    ),
  );

  saveTo("update", updatedMessage);
};
