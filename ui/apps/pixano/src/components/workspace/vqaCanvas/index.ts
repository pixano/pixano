/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// Exports
export { default as VqaArea } from "./VqaArea.svelte";
export type {
  MessageGenerationPrompts,
  PixanoInferenceCompletionModel,
  PromptByQuestionType,
} from "$lib/stores/vqaStores.svelte";
export type { LabelFormat, StoreQuestionEvent } from "$lib/types/vqa";
export {
  ContentChangeEventType,
  isNewAnswerEvent,
  isUpdatedMessageEvent,
} from "$lib/types/vqa";
export type {
  ContentChangeEvent,
  DeleteQuestionEvent,
  GenerateAnswerEvent,
  NewAnswerEvent,
  UpdatedMessageEvent,
} from "$lib/types/vqa";
