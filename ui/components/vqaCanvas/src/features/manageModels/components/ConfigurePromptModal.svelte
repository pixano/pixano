<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { createEventDispatcher, onMount, tick } from "svelte";

  import { PrimaryButton, QuestionTypeEnum } from "@pixano/core";

  import { completionModelsStore } from "../../../stores/completionModels";

  export let vqaSectionWidth: number;

  let question_type = QuestionTypeEnum.OPEN; //TODO selector to choose question type
  let textarea: HTMLTextAreaElement | null = null;

  let completionPrompt =
    $completionModelsStore.find((m) => m.selected)?.prompts[question_type] ?? "";

  onMount(() => resizeTextarea());

  const resizeTextarea = async () => {
    if (textarea) {
      textarea.style.height = "auto";
      await tick();
      textarea.style.height = textarea.scrollHeight + "px";
    }
  };

  const dispatch = createEventDispatcher();

  function handleSavePrompt() {
    console.log("Save prompt", completionPrompt);
    dispatch("cancelPrompt"); //also close modal
  }

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
    <p>Prompt settings</p>
  </div>

  <div class="px-3 pb-3 flex flex-col gap-2">
    <textarea
      placeholder="Enter your prompt here"
      class="p-2 border rounded-lg border-gray-200 outline-none text-slate-800 focus:border-primary resize-none overflow-hidden"
      bind:this={textarea}
      bind:value={completionPrompt}
    />

    <div class="flex flex-row gap-2 px-3 justify-center">
      <PrimaryButton on:click={handleCancel}>Cancel</PrimaryButton>
      <PrimaryButton on:click={handleSavePrompt} isSelected disabled={completionPrompt === ""}>
        Save
      </PrimaryButton>
    </div>
  </div>
</div>
