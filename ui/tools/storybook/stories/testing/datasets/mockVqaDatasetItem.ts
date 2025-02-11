/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  BaseSchema,
  BBox,
  Conversation,
  DatasetItem,
  Entity,
  Item,
  Mask,
  Message,
  MessageTypeEnum,
  QuestionTypeEnum,
  WorkspaceType,
  type BBoxType,
  type MaskType,
  type MessageType,
} from "@pixano/core";

import { mockAnnotationType, mockEntityType, mockImage, mockMessageType } from "../shared";

const bboxData: BBoxType = {
  coords: [0.7411248087882996, 0.031893156468868256, 0.21801991760730743, 0.27492383122444153],
  format: "xywh",
  is_normalized: true,
  confidence: 1,
};

/* eslint-disable @typescript-eslint/no-unused-vars */
// The unused variables will be used in future commits
const bbox = new BBox({
  id: "bbox_id",
  table_info: { name: "bbox", group: "annotations", base_schema: BaseSchema.BBox },
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  data: { ...bboxData, ...mockAnnotationType },
});

const maskData: MaskType[] = [
  {
    size: [513, 770],
    counts: [
      157152, 6, 506, 10, 502, 15, 496, 21, 491, 25, 486, 31, 481, 36, 475, 41, 471, 46, 466, 51,
      460, 56, 456, 61, 450, 67, 445, 71, 440, 77, 435, 82, 430, 86, 425, 92, 420, 97, 414, 102,
      410, 107, 404, 113, 399, 117, 394, 123, 389, 128, 384, 132, 379, 138, 374, 143, 368, 148, 364,
      153, 358, 155, 357, 156, 356, 157, 354, 159, 353, 160, 351, 162, 350, 163, 348, 165, 347, 166,
      346, 167, 344, 169, 343, 169, 342, 171, 341, 172, 339, 174, 338, 175, 337, 176, 335, 178, 334,
      179, 332, 181, 331, 182, 331, 182, 331, 181, 332, 181, 332, 181, 332, 181, 332, 181, 332, 181,
      332, 181, 332, 181, 332, 181, 332, 181, 332, 181, 332, 180, 333, 180, 333, 180, 333, 180, 333,
      180, 333, 180, 333, 180, 333, 180, 333, 180, 333, 180, 333, 180, 333, 179, 334, 179, 334, 179,
      334, 179, 334, 179, 334, 179, 334, 179, 334, 179, 334, 179, 334, 179, 334, 179, 334, 178, 335,
      178, 335, 178, 335, 178, 335, 178, 335, 178, 335, 178, 335, 178, 335, 178, 335, 178, 335, 178,
      335, 177, 336, 177, 336, 177, 336, 177, 336, 177, 336, 177, 336, 177, 336, 177, 336, 177, 336,
      177, 336, 177, 336, 176, 337, 176, 337, 176, 337, 176, 337, 176, 337, 176, 337, 176, 337, 176,
      337, 176, 337, 176, 337, 176, 337, 175, 338, 175, 338, 175, 338, 175, 338, 175, 338, 175, 338,
      175, 338, 175, 338, 175, 338, 175, 338, 174, 339, 174, 339, 174, 339, 174, 339, 174, 339, 174,
      339, 174, 339, 174, 339, 174, 339, 174, 339, 174, 339, 173, 340, 173, 340, 173, 340, 173, 340,
      173, 340, 173, 340, 173, 340, 173, 340, 173, 340, 173, 340, 173, 340, 172, 341, 172, 341, 172,
      341, 172, 341, 172, 341, 172, 341, 172, 341, 172, 341, 172, 341, 172, 341, 172, 341, 171, 342,
      171, 342, 171, 342, 171, 342, 171, 342, 171, 342, 171, 342, 171, 342, 171, 342, 171, 342, 171,
      342, 170, 343, 170, 343, 170, 343, 170, 343, 170, 343, 170, 343, 170, 343, 170, 343, 170, 343,
      170, 343, 170, 343, 169, 344, 169, 344, 169, 344, 169, 344, 169, 344, 169, 344, 169, 350, 163,
      356, 157, 362, 151, 369, 144, 375, 137, 382, 131, 388, 125, 394, 119, 400, 113, 406, 107, 413,
      100, 419, 94, 425, 88, 431, 82, 437, 76, 443, 69, 451, 62, 457, 56, 463, 50, 469, 44, 475, 38,
      481, 32, 487, 26, 494, 19, 500, 13, 506, 7, 127467,
    ],
  },
  {
    size: [513, 770],
    counts: [
      128120, 29, 483, 57, 454, 61, 451, 64, 448, 67, 444, 70, 442, 73, 438, 77, 435, 80, 431, 84,
      428, 86, 426, 89, 422, 93, 419, 96, 415, 100, 412, 102, 408, 107, 404, 111, 399, 116, 395,
      119, 392, 123, 387, 127, 384, 130, 380, 133, 378, 136, 376, 138, 374, 140, 372, 141, 371, 143,
      369, 145, 367, 147, 366, 147, 365, 149, 363, 151, 361, 153, 359, 154, 358, 156, 356, 158, 354,
      160, 352, 161, 352, 162, 350, 164, 348, 166, 346, 167, 345, 169, 343, 171, 340, 174, 338, 175,
      337, 177, 335, 179, 333, 181, 330, 183, 329, 185, 327, 187, 325, 189, 323, 190, 321, 193, 319,
      194, 318, 195, 317, 196, 316, 197, 316, 197, 316, 197, 316, 198, 315, 198, 314, 199, 314, 199,
      314, 199, 314, 199, 314, 199, 314, 199, 313, 201, 312, 201, 312, 201, 312, 201, 312, 201, 311,
      202, 311, 202, 311, 203, 310, 203, 310, 203, 310, 203, 309, 204, 309, 204, 309, 204, 309, 204,
      309, 205, 307, 206, 307, 206, 307, 206, 307, 206, 307, 206, 307, 206, 307, 207, 306, 207, 306,
      207, 306, 207, 306, 207, 306, 207, 306, 207, 306, 207, 306, 207, 306, 207, 306, 206, 307, 206,
      307, 206, 307, 205, 308, 205, 308, 204, 309, 204, 309, 204, 309, 203, 310, 203, 310, 202, 311,
      202, 311, 202, 311, 201, 312, 201, 312, 200, 313, 200, 313, 200, 313, 199, 314, 199, 314, 198,
      315, 198, 315, 197, 316, 197, 316, 197, 316, 196, 317, 196, 317, 195, 318, 195, 318, 195, 318,
      194, 319, 194, 320, 192, 321, 191, 323, 189, 325, 188, 325, 187, 327, 185, 328, 184, 330, 182,
      332, 180, 333, 179, 335, 177, 337, 175, 338, 174, 340, 173, 352, 160, 366, 146, 368, 144, 370,
      142, 372, 140, 375, 137, 377, 135, 379, 133, 381, 132, 382, 130, 385, 127, 387, 125, 389, 123,
      391, 121, 393, 119, 396, 116, 398, 114, 400, 111, 403, 109, 406, 105, 409, 103, 411, 100, 414,
      98, 416, 95, 420, 92, 422, 89, 426, 86, 429, 82, 433, 79, 436, 75, 440, 72, 443, 68, 447, 65,
      450, 61, 454, 58, 457, 54, 461, 51, 464, 47, 468, 44, 170911,
    ],
  },
];

const masks = maskData.map(
  (data, index) =>
    new Mask({
      id: `mask_id_${index}`,
      table_info: { name: "mask", group: "annotations", base_schema: BaseSchema.Mask },
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      data: { ...data, ...mockAnnotationType },
    }),
);

const entity = new Entity({
  id: `entity_id`,
  table_info: { name: "entity", group: "entity", base_schema: BaseSchema.Entity },
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  data: mockEntityType,
});

const conversation = new Conversation({
  id: `conversation_id`,
  table_info: { name: "conversation", group: "entity", base_schema: BaseSchema.Conversation },
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  data: {
    kind: "conversation",
    with_model: { id: "model_id", name: "model_name" },
    ...mockEntityType,
  },
});

const messagesData: MessageType[] = [
  {
    number: 0,
    user: "user",
    type: MessageTypeEnum.QUESTION,
    content:
      "Calculate the area of the zero circle with the following data:<image 1>Assume that the tracing arm of the planimeter was so set that one revolution of the measuring wheel measures 100 $cm^{2}$ on the paper.",
    timestamp: new Date().toISOString(),
    choices: [],
    question_type: QuestionTypeEnum.OPEN,
  },
  {
    number: 0,
    user: "user",
    type: MessageTypeEnum.ANSWER,
    content: "1970.6",
    timestamp: new Date().toISOString(),
    answers: [""],
    explanations: [""],
  },
  {
    number: 1,
    user: "user",
    type: MessageTypeEnum.QUESTION,
    content:
      "Each of the following situations relates to a different company. <image 1> For company B, find the missing amounts.",
    timestamp: new Date().toISOString(),
    choices: ["$63,020", "$58,410", "$71,320", "$77,490"],
    question_type: QuestionTypeEnum.SINGLE_CHOICE,
  },
  {
    number: 1,
    user: "user",
    type: MessageTypeEnum.ANSWER,
    content: "",
    timestamp: new Date().toISOString(),
    answers: [""],
    explanations: [""],
  },
  {
    number: 2,
    user: "user",
    type: MessageTypeEnum.QUESTION,
    content:
      "<image 1> by Mark Gertler can be found in the Touchstones Rochdale museum. Which artist belonging to the Bloomsbury group was Gertler in a relationship with?",
    timestamp: new Date().toISOString(),
    choices: ["Vanessa Bell", "Eileen Agar", "Dora Carrington", "Leonora Carrington"],
    question_type: QuestionTypeEnum.MULTI_CHOICE_EXPLANATION,
  },
  {
    number: 2,
    user: "user",
    type: MessageTypeEnum.ANSWER,
    content:
      "[[C]] Gertler and Carrington met at the Slade School of Fine Art in the early 1910s, alongside their friend and fellow artist Richard Nevinson. When both men fell in love with Carrington, Gertler wrote to Nevinson: 'I am writing here to tell you that our friendship must end from now, my sole reason being that I am in love with Carrington and I have reason to believe that you are so too. Therefore, much as I have tried to overlook it, I have come to the conclusion that rivals, and rivals in love, cannot be friends.' Image: The Bokhara Coat, 1920, Mark Gertler (1891-1939); Bridgeman Images",
    timestamp: new Date().toISOString(),
    answers: ["C"],
    explanations: [
      "Gertler and Carrington met at the Slade School of Fine Art in the early 1910s, alongside their friend and fellow artist Richard Nevinson. When both men fell in love with Carrington, Gertler wrote to Nevinson: 'I am writing here to tell you that our friendship must end from now, my sole reason being that I am in love with Carrington and I have reason to believe that you are so too. Therefore, much as I have tried to overlook it, I have come to the conclusion that rivals, and rivals in love, cannot be friends.' Image: The Bokhara Coat, 1920, Mark Gertler (1891-1939); Bridgeman Images",
    ],
  },
];

const messages = messagesData.map(
  (data, index) =>
    new Message({
      id: `message_id_${index}`,
      table_info: { name: "messages", group: "annotations", base_schema: BaseSchema.Message },
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      data: {
        ...data,
        ...mockMessageType,
      },
    }),
);

const item = new Item({
  id: "item_id",
  table_info: { name: "item", group: "item", base_schema: BaseSchema.Item },
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  data: {},
});

export const mockVqaDatasetItem: DatasetItem = {
  item,
  entities: {
    multimodal_entity: [entity],
    conversations: [conversation],
  },
  annotations: {
    messages,
    masks,
    bboxes: [bbox],
  },
  views: {
    image: mockImage,
  },
  ui: {
    datasetId: "dataset_id",
    type: WorkspaceType.IMAGE_VQA,
  },
};
