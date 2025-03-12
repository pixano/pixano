<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { createEventDispatcher } from "svelte";

  import {
    AutoResizeTextarea,
    Input,
    MessageTypeEnum,
    PrimaryButton,
    QuestionTypeEnum,
    type InputEvents,
  } from "@pixano/core";

  import { completionModelsStore } from "../../../stores/completionModels";

  export let vqaSectionWidth: number;

  let question_type = QuestionTypeEnum.OPEN;
  const list_qt = Object.values(QuestionTypeEnum).map((value) => ({
    value,
    label: value,
  }));

  let message_type = MessageTypeEnum.QUESTION;
  const list_mt = Object.values(MessageTypeEnum).map((value) => ({
    value,
    label: value,
  }));

  let completionPrompt: string = "";
  $: selectPrompt(question_type, message_type);

  const selectPrompt = (qtype: QuestionTypeEnum, mtype: MessageTypeEnum) => {
    completionPrompt = $completionModelsStore.find((m) => m.selected)?.prompts[mtype][qtype] ?? "";
  };

  let completionImageRegex = $completionModelsStore.find((m) => m.selected)?.regex.image ?? null;
  let completionObjectRegex = $completionModelsStore.find((m) => m.selected)?.regex.object ?? null;

  const dispatch = createEventDispatcher();

  function handleSavePrompt() {
    completionModelsStore.update((models) =>
      models.map((model) =>
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
              regex: {
                image: completionImageRegex ?? "",
                object: completionObjectRegex ?? "",
              },
            }
          : model,
      ),
    );
    dispatch("cancelPrompt"); //also close modal
  }

  const handleChangeRegex = (event: InputEvents["change"]) => {
    if (event.target && "name" in event.target && "value" in event.target) {
      const name: string = event.target.name as string;
      const value: string = event.target.value as string;
      switch (name) {
        case "image_regex":
          completionImageRegex = value;
          break;
        case "object_regex":
          completionObjectRegex = value;
          break;
      }
    }
  };

  function handleCancel() {
    dispatch("cancelPrompt");
  }
</script>

<!-- stop propagation to prevent from closing the modal when clicking on the background -->
<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div
  on:click|stopPropagation={() => {}}
  class="fixed top-[calc(80px+5px)] z-50 overflow-y-auto w-80 rounded-md bg-white text-slate-800 flex flex-col gap-3"
  style={`left: calc(${vqaSectionWidth}px + 10px);`}
>
  <div class="bg-primary p-3 rounded-b-none rounded-t-md text-white">
    <p>Regex settings</p>
  </div>

  <div class="px-3 pb-3 flex flex-col gap-2">
    <h5 class="font-medium">Image regex</h5>
    <Input
      name="image_regex"
      value={completionImageRegex}
      type="string"
      on:change={handleChangeRegex}
      on:keyup={(e) => e.stopPropagation()}
    />
    <h5 class="font-medium">Object regex</h5>
    <Input
      name="object_regex"
      value={completionObjectRegex}
      type="string"
      on:change={handleChangeRegex}
      on:keyup={(e) => e.stopPropagation()}
    />
  </div>

  <div class="bg-primary p-3 rounded-b-none rounded-t-md text-white">
    <p>Prompt settings</p>
  </div>

  <div class="px-3 pb-3 flex flex-col gap-2">
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

    <div class="flex flex-row gap-2 px-3 justify-center">
      <PrimaryButton on:click={handleCancel}>Cancel</PrimaryButton>
      <PrimaryButton on:click={handleSavePrompt} isSelected disabled={completionPrompt === ""}>
        Save
      </PrimaryButton>
    </div>
  </div>
</div>
