/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { isQuestionData, QuestionTypeEnum, type Message, type SaveItem } from "@pixano/core";

import { addOrUpdateSaveItem } from "../../api/objectsApi";
import { createNewAnswer } from "../../utils/createNewAnswer";
import { annotations, saveData } from "../datasetItemWorkspaceStores";

export const generateAnswer = (question: Message) => {
  const questionData = question.data;

  if (!isQuestionData(questionData)) {
    console.error("ERROR: Message is not a question");
    return;
  }

  const newAnswer = createAnswer({ question, questionType: questionData.question_type });

  annotations.update((prevAnnotations) => [...prevAnnotations, newAnswer]);

  const save_item: SaveItem = {
    change_type: "add",
    object: newAnswer,
  };

  saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
};

const createAnswer = ({
  question,
  questionType,
}: {
  question: Message;
  questionType: QuestionTypeEnum;
}) => {
  const answerContent =
    questionType === QuestionTypeEnum.OPEN
      ? "This is a mock answer"
      : "[[A]] This is a mock answer";

  return createNewAnswer({ question, content: answerContent });
};
