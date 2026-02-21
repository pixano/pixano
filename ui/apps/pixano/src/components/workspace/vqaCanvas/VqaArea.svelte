<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Message, MessageTypeEnum } from "$lib/types/dataset";
  import type { InferenceModel, InferenceServerState } from "$lib/types/inference";
  import type { StoreQuestionEvent } from "$lib/types/vqa";
  import type {
    ContentChangeEvent,
    DeleteQuestionEvent,
    GenerateAnswerEvent,
  } from "$lib/types/vqa";
  import type { PixanoInferenceCompletionModel } from "$lib/stores/vqaStores.svelte";

  import VqaChatThread from "./annotateItem/VqaChatThread.svelte";
  import VqaHeader from "./annotateItem/VqaHeader.svelte";
  import VqaInputArea from "./annotateItem/VqaInputArea.svelte";
  import { isQuestionCompleted } from "./annotateItem/utils";
  import { groupMessagesByNumber } from "./utils";


  interface Props {
    messages: Message[];
    vqaSectionWidth: number;
    inferenceServer: InferenceServerState;
    vqaModels: InferenceModel[];
    completionModels: PixanoInferenceCompletionModel[];
    onCompletionModelsChange?: (models: PixanoInferenceCompletionModel[]) => void;
    onStoreQuestion?: (event: StoreQuestionEvent) => void;
    onAnswerContentChange?: (event: ContentChangeEvent) => void;
    onGenerateAnswer?: (event: GenerateAnswerEvent) => void;
    onDeleteQuestion?: (event: DeleteQuestionEvent) => void;
    onGenerateQuestion?: (
      completionModel: string,
    ) => Promise<{ content: string; choices: string[] } | null>;
  }

  let {
    messages,
    vqaSectionWidth,
    inferenceServer,
    vqaModels,
    completionModels,
    onCompletionModelsChange,
    onStoreQuestion,
    onAnswerContentChange,
    onGenerateAnswer,
    onDeleteQuestion,
    onGenerateQuestion,
  }: Props = $props();

  let messagesByNumber = $derived(groupMessagesByNumber(messages));

  // Find the last question group and check if it has an answer

  let lastGroup = $derived(messagesByNumber.length > 0 ? messagesByNumber[messagesByNumber.length - 1] : null);

  let pendingQuestion =
    $derived(lastGroup && !isQuestionCompleted(lastGroup)
      ? lastGroup.find((m) => m.data.type === MessageTypeEnum.QUESTION)
      : null);
</script>

<div class="flex flex-col h-full bg-card overflow-hidden">
  <VqaHeader {vqaSectionWidth} {inferenceServer} {vqaModels} {completionModels} {onCompletionModelsChange} />

  <div class="flex-1 overflow-hidden">
    <VqaChatThread
      {messagesByNumber}
      {completionModels}
      {onAnswerContentChange}
      {onGenerateAnswer}
      {onDeleteQuestion}
    />
  </div>

  <VqaInputArea
    {pendingQuestion}
    {completionModels}
    {onStoreQuestion}
    {onAnswerContentChange}
    {onGenerateAnswer}
    {onGenerateQuestion}
  />
</div>

<style>
</style>
