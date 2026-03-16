<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { PixanoInferenceCompletionModel } from "$lib/stores/vqaStores.svelte";
  import { MessageTypeEnum, QuestionTypeEnum } from "$lib/types/dataset";
  import { AutoResizeTextarea, Input, PrimaryButton } from "$lib/ui";

  interface Props {
    vqaSectionWidth: number;
    completionModels: PixanoInferenceCompletionModel[];
    onCompletionModelsChange?: (models: PixanoInferenceCompletionModel[]) => void;
    onCancelPrompt?: () => void;
  }

  let { vqaSectionWidth, completionModels, onCompletionModelsChange, onCancelPrompt }: Props =
    $props();

  let question_type = $state(QuestionTypeEnum.OPEN);
  const list_qt = Object.values(QuestionTypeEnum).map((value) => ({
    value,
    label: value,
  }));

  let message_type = $state(MessageTypeEnum.QUESTION);
  const list_mt = Object.values(MessageTypeEnum).map((value) => ({
    value,
    label: value,
  }));

  let completionPrompt: string = $state("");

  const selectPrompt = (qtype: QuestionTypeEnum, mtype: MessageTypeEnum) => {
    completionPrompt = completionModels.find((m) => m.selected)?.prompts[mtype][qtype] ?? "";
  };

  // svelte-ignore state_referenced_locally
  let temperature = $state(completionModels.find((m) => m.selected)?.temperature ?? 1.0);

  function handleSavePrompt() {
    onCompletionModelsChange?.(
      completionModels.map((model) =>
        model.selected
          ? {
              ...model,
              prompts: {
                ...model.prompts,
                [message_type]: {
                  ...model.prompts[message_type],
                  as_system: true,
                  [question_type]: completionPrompt,
                },
              },
              temperature,
            }
          : model,
      ),
    );
    onCancelPrompt?.(); //also close modal
  }

  function handleCancel() {
    onCancelPrompt?.();
  }
  $effect(() => {
    selectPrompt(question_type, message_type);
  });
</script>

<!-- stop propagation to prevent from closing the modal when clicking on the background -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  onclick={(event) => event.stopPropagation()}
  class="fixed top-[calc(80px+5px)] z-50 overflow-y-auto w-80 rounded-md bg-card text-foreground flex flex-col gap-3 pb-3"
  style={`left: calc(${vqaSectionWidth}px + 10px);`}
>
  <div class="bg-primary p-3 rounded-b-none rounded-t-md text-white">
    <p>Prompt settings</p>
  </div>
  <div class="px-3 flex flex-col gap-2">
    <h5 class="font-medium">Question type</h5>
    <select
      class="z-50 w-full rounded-md border bg-popover p-2 text-popover-foreground shadow-md outline-none"
      bind:value={question_type}
    >
      {#each list_qt as qt}
        {#if qt.value === question_type}
          <option value={qt.value} selected>{qt.label}</option>
        {:else}
          <option value={qt.value}>{qt.label}</option>
        {/if}
      {/each}
    </select>
    <h5 class="font-medium">Message type</h5>
    <select
      class="z-50 w-full rounded-md border bg-popover p-2 text-popover-foreground shadow-md outline-none"
      bind:value={message_type}
    >
      {#each list_mt as mt}
        {#if mt.value === message_type}
          <option value={mt.value} selected>{mt.label}</option>
        {:else}
          <option value={mt.value}>{mt.label}</option>
        {/if}
      {/each}
    </select>
    <h5 class="font-medium">Prompt</h5>
    <AutoResizeTextarea placeholder="Enter your prompt here" bind:value={completionPrompt} />
  </div>
  <div class="bg-primary p-3 rounded-b-none rounded-t-md text-white">
    <p>Model settings</p>
  </div>
  <div class="px-3 flex flex-col gap-2">
    <h5 class="font-medium">Temperature</h5>
    <Input
      bind:value={temperature}
      type="string"
      onkeyup={(e: KeyboardEvent) => {
        e.stopPropagation();
      }}
    />
  </div>
  <div class="flex flex-row gap-2 px-3 justify-center">
    <PrimaryButton onclick={handleCancel}>Cancel</PrimaryButton>
    <PrimaryButton onclick={handleSavePrompt} isSelected disabled={completionPrompt === ""}>
      Save
    </PrimaryButton>
  </div>
</div>
