<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { X } from "phosphor-svelte";

  import type { PixanoInferenceCompletionModel } from "$lib/stores/vqaStores.svelte";
  import { answerTaskBody, questionTaskBody } from "$lib/stores/workspaceMutations";
  import { MessageTypeEnum, QuestionTypeEnum } from "$lib/types/dataset";

  interface Props {
    completionModels: PixanoInferenceCompletionModel[];
    onCompletionModelsChange?: (models: PixanoInferenceCompletionModel[]) => void;
    onCancelPrompt?: () => void;
  }

  let { completionModels, onCompletionModelsChange, onCancelPrompt }: Props = $props();

  const messageTypes = [
    { value: MessageTypeEnum.QUESTION, label: "Question" },
    { value: MessageTypeEnum.ANSWER, label: "Answer" },
  ];

  const questionTypes = [
    { value: QuestionTypeEnum.OPEN, label: "Open" },
    { value: QuestionTypeEnum.SINGLE_CHOICE, label: "Yes / No" },
    { value: QuestionTypeEnum.MULTI_CHOICE, label: "Multiple Choice" },
  ];

  let messageType = $state(MessageTypeEnum.QUESTION);
  let questionType = $state(QuestionTypeEnum.OPEN);
  let prompt = $state("");

  // svelte-ignore state_referenced_locally
  let temperature = $state(completionModels.find((m) => m.selected)?.temperature ?? 0.7);
  // svelte-ignore state_referenced_locally
  let includeHistory = $state(completionModels.find((m) => m.selected)?.includeHistory ?? false);

  function loadPrompt(mt: MessageTypeEnum, qt: QuestionTypeEnum) {
    prompt = completionModels.find((m) => m.selected)?.prompts[mt][qt] ?? "";
  }

  $effect(() => {
    loadPrompt(messageType, questionType);
  });

  let userPromptPreview = $derived.by(() => {
    if (messageType === MessageTypeEnum.QUESTION) {
      return questionTaskBody(questionType, includeHistory);
    }
    return answerTaskBody(questionType, "{question content}", ["{choice A}", "{choice B}"]);
  });

  function handleSave() {
    onCompletionModelsChange?.(
      completionModels.map((model) =>
        model.selected
          ? {
              ...model,
              prompts: {
                ...model.prompts,
                [messageType]: {
                  ...model.prompts[messageType],
                  [questionType]: prompt,
                },
              },
              temperature,
              includeHistory,
            }
          : model,
      ),
    );
    onCancelPrompt?.();
  }

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === "Escape") onCancelPrompt?.();
  }
</script>

<svelte:window onkeydown={handleKeyDown} />

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
  onclick={onCancelPrompt}
>
  <div
    onclick={(e) => e.stopPropagation()}
    class="w-[42rem] h-[44rem] flex flex-col rounded-2xl bg-card border border-border/50 shadow-2xl"
  >
    <!-- Header -->
    <div class="flex items-center justify-between px-6 pt-6 pb-4 shrink-0">
      <h2 class="text-base font-semibold text-foreground">VLM Configuration</h2>
      <button
        type="button"
        onclick={onCancelPrompt}
        class="h-7 w-7 flex items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
      >
        <X weight="regular" size={16} />
      </button>
    </div>

    <!-- Content -->
    <div class="flex flex-col flex-1 overflow-hidden px-6 pb-6 gap-4">
      <!-- Message type segmented control -->
      <div class="flex rounded-lg bg-muted p-1 gap-1 shrink-0">
        {#each messageTypes as mt}
          <button
            type="button"
            onclick={() => (messageType = mt.value)}
            class="flex-1 px-3 py-1.5 rounded-md text-[13px] font-medium transition-all duration-150
              {messageType === mt.value
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground'}"
          >
            {mt.label}
          </button>
        {/each}
      </div>

      <!-- Question type segmented control -->
      <div class="space-y-2 shrink-0">
        <span class="text-[13px] font-medium text-muted-foreground">Question Type</span>
        <div class="flex rounded-lg bg-muted p-1 gap-1">
          {#each questionTypes as qt}
            <button
              type="button"
              onclick={() => (questionType = qt.value)}
              class="flex-1 px-2 py-1.5 rounded-md text-[12px] font-medium transition-all duration-150
                {questionType === qt.value
                ? 'bg-background text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground'}"
            >
              {qt.label}
            </button>
          {/each}
        </div>
      </div>

      <!-- Prompts area (takes remaining space) -->
      <div class="flex flex-col flex-1 min-h-0 gap-3">
        <!-- System prompt (editable) -->
        <div class="flex flex-col flex-1 min-h-0 space-y-1.5">
          <span class="text-[13px] font-medium text-muted-foreground shrink-0">System Prompt</span>
          <div
            class="flex-1 min-h-0 rounded-xl border border-border bg-muted/30 focus-within:border-primary/50 focus-within:ring-4 focus-within:ring-primary/5 focus-within:bg-card transition-all"
          >
            <textarea
              placeholder="Enter instructions for the model..."
              bind:value={prompt}
              class="w-full h-full bg-transparent border-none focus:ring-0 focus:outline-none py-2.5 px-3.5 text-[13px] text-foreground leading-relaxed placeholder:text-muted-foreground resize-none overflow-y-auto"
            ></textarea>
          </div>
        </div>

        <!-- User prompt template (read-only preview) -->
        <div class="flex flex-col flex-1 min-h-0 space-y-1.5">
          <span class="text-[13px] font-medium text-muted-foreground shrink-0"
            >User Prompt Template
            <span class="text-[11px] font-normal opacity-60">(auto-generated, read-only)</span>
          </span>
          <div
            class="flex-1 min-h-0 rounded-xl border border-border/50 bg-muted/50 overflow-y-auto"
          >
            <pre
              class="py-2.5 px-3.5 text-[12px] leading-relaxed text-muted-foreground font-sans whitespace-pre-wrap break-words"
            >{userPromptPreview}</pre>
          </div>
        </div>
      </div>

      <!-- Temperature slider -->
      <div class="space-y-1.5 shrink-0">
        <div class="flex items-center justify-between">
          <span class="text-[13px] font-medium text-muted-foreground">Temperature</span>
          <span class="text-[13px] font-mono font-medium text-foreground tabular-nums">
            {temperature.toFixed(1)}
          </span>
        </div>
        <input
          type="range"
          min="0"
          max="1"
          step="0.1"
          bind:value={temperature}
          class="w-full h-1.5 rounded-full appearance-none cursor-pointer accent-primary bg-muted"
        />
        <div class="flex justify-between text-[11px] text-muted-foreground">
          <span>Precise</span>
          <span>Creative</span>
        </div>
      </div>

      <!-- History toggle + Save -->
      <div class="flex items-center justify-between shrink-0">
        <label class="flex items-center gap-3 cursor-pointer">
          <div class="relative">
            <input type="checkbox" bind:checked={includeHistory} class="sr-only peer" />
            <div
              class="w-9 h-5 rounded-full transition-colors peer-checked:bg-primary bg-muted border border-border"
            ></div>
            <div
              class="absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-background shadow-sm transition-transform peer-checked:translate-x-4"
            ></div>
          </div>
          <span class="text-[13px] text-muted-foreground">Include conversation history</span>
        </label>

        <button
          type="button"
          onclick={handleSave}
          class="px-6 py-2 rounded-xl bg-primary text-primary-foreground text-sm font-medium shadow-sm hover:bg-primary/90 transition-colors"
        >
          Save Changes
        </button>
      </div>
    </div>
  </div>
</div>
