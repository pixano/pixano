<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { PixanoInferenceCompletionModel } from "$lib/stores/vqaStores.svelte";
  import type { ContentChangeEvent, DeleteQuestionEvent, GenerateAnswerEvent, QuestionThread } from "$lib/types/vqa";

  import QuestionForm from "./QuestionForm.svelte";

  interface Props {
    questionThreads: QuestionThread[];
    completionModels: PixanoInferenceCompletionModel[];
    onAnswerContentChange?: (event: ContentChangeEvent) => void;
    onGenerateAnswer?: (event: GenerateAnswerEvent) => void;
    onDeleteQuestion?: (event: DeleteQuestionEvent) => void;
  }

  let { questionThreads, completionModels, onAnswerContentChange, onGenerateAnswer, onDeleteQuestion }: Props =
    $props();
  let scrollContainer: HTMLDivElement | undefined = $state();

  $effect(() => {
    if (scrollContainer) {
      scrollContainer.scrollTo({
        top: scrollContainer.scrollHeight,
        behavior: "smooth",
      });
    }
  });
</script>

<div
  class="p-4 space-y-8 flex flex-col h-full overflow-y-auto custom-scrollbar"
  bind:this={scrollContainer}
>
  {#if questionThreads.length === 0}
    <div class="flex flex-col items-center justify-center py-20 text-center space-y-4 m-auto">
      <div
        class="w-16 h-16 bg-muted rounded-full flex items-center justify-center text-muted-foreground"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z" />
          <path d="M8 12h.01" />
          <path d="M12 12h.01" />
          <path d="M16 12h.01" />
        </svg>
      </div>
      <div>
        <h3 class="font-medium text-foreground">No questions yet</h3>
        <p class="text-sm text-muted-foreground max-w-[200px] mx-auto">
          Ask a question about the image to start the conversation.
        </p>
      </div>
    </div>
  {:else}
    {#each questionThreads as thread}
      <div class="relative">
        <QuestionForm
          {thread}
          {completionModels}
          {onAnswerContentChange}
          {onGenerateAnswer}
          {onDeleteQuestion}
        />
      </div>
    {/each}
  {/if}
</div>

<style>
  .custom-scrollbar::-webkit-scrollbar {
    width: 6px;
  }
  .custom-scrollbar::-webkit-scrollbar-track {
    background: transparent;
  }
  .custom-scrollbar::-webkit-scrollbar-thumb {
    background: hsl(var(--border));
    border-radius: 3px;
  }
  .custom-scrollbar::-webkit-scrollbar-thumb:hover {
    background: hsl(var(--muted-foreground));
  }
</style>
