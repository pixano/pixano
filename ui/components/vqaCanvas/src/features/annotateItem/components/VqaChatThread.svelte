<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { afterUpdate } from "svelte";

  import type { Message } from "@pixano/core";

  import QuestionForm from "./QuestionForm.svelte";

  export let messagesByNumber: Message[][];

  let scrollContainer: HTMLDivElement;

  afterUpdate(() => {
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
  {#if messagesByNumber.length === 0}
    <div class="flex flex-col items-center justify-center py-20 text-center space-y-4 m-auto">
      <div
        class="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center text-slate-400"
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
        <h3 class="font-medium text-slate-900">No questions yet</h3>
        <p class="text-sm text-slate-500 max-w-[200px] mx-auto">
          Ask a question about the image to start the conversation.
        </p>
      </div>
    </div>
  {:else}
    {#each messagesByNumber as messages}
      <div class="relative">
        <QuestionForm bind:messages on:answerContentChange on:generateAnswer on:deleteQuestion />
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
    background: #e2e8f0;
    border-radius: 3px;
  }
  .custom-scrollbar::-webkit-scrollbar-thumb:hover {
    background: #cbd5e1;
  }
</style>
