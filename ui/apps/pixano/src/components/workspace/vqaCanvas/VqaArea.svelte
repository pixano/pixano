<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { isQuestionCompleted } from "./annotateItem/utils";
  import VqaChatThread from "./annotateItem/VqaChatThread.svelte";
  import VqaHeader from "./annotateItem/VqaHeader.svelte";
  import VqaInputArea from "./annotateItem/VqaInputArea.svelte";
  import type { PixanoInferenceCompletionModel } from "$lib/stores/vqaStores.svelte";
  import { Message } from "$lib/types/dataset";
  import type {
    InferenceModel,
    InferenceModelSelection,
    InferenceServerState,
  } from "$lib/types/inference";
  import type {
    ContentChangeEvent,
    DeleteQuestionEvent,
    GenerateAnswerEvent,
    StoreQuestionEvent,
  } from "$lib/types/vqa";
  import { buildQuestionThreads } from "$lib/utils/vqaThreads";

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
    onGenerateQuestion?: (completionModel: InferenceModelSelection) => Promise<{
      content: string;
      choices: string[];
      question_type: import("$lib/types/dataset").QuestionTypeEnum;
    } | null>;
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

  let questionThreads = $derived(buildQuestionThreads(messages));
  let lastThread = $derived(
    questionThreads.length > 0 ? questionThreads[questionThreads.length - 1] : null,
  );
  let pendingQuestion = $derived(
    lastThread && !isQuestionCompleted(lastThread.messages) ? lastThread.question : null,
  );
</script>

<div class="flex flex-col h-full bg-card overflow-hidden">
  <VqaHeader
    {vqaSectionWidth}
    {inferenceServer}
    {vqaModels}
    {completionModels}
    {onCompletionModelsChange}
  />

  <div class="flex-1 overflow-hidden">
    <VqaChatThread
      {questionThreads}
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
