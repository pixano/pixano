<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { createEventDispatcher, tick } from "svelte";

  import { MultimodalImageNLPTask, PrimaryButton, QuestionTypeEnum } from "@pixano/core";

  import { pixanoInferenceStore } from "../../../../../apps/pixano/src/lib/stores/datasetStores";

  let question_type = QuestionTypeEnum.OPEN; //TODO selector to choose question type

  let textarea: HTMLTextAreaElement | null = null;

  let current_content = "";

  pixanoInferenceStore.subscribe((pis) => {
    const filteredPis = pis.filter(
      (pi) => pi.selected && pi.task === MultimodalImageNLPTask.CONDITIONAL_GENERATION,
    );
    if (filteredPis && filteredPis.length === 1) {
      const current_pi = filteredPis[0];
      const filteredPrompt = current_pi.prompts.filter(
        (prompt) => prompt.question_type === question_type,
      );
      if (filteredPrompt && filteredPrompt.length === 1) {
        const current_prompt = filteredPrompt[0];
        current_content = current_prompt.content;
      }
    }
  });
  $: if (current_content) {
    void adjustHeight();
  }

  const adjustHeight = async () => {
    if (textarea) {
      textarea.style.height = "auto";
      await tick();
      textarea.style.height = textarea.scrollHeight + "px";
    }
  };

  const dispatch = createEventDispatcher();

  function handleOK() {
    console.log("PROMPT", current_content);
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
  class="fixed top-[calc(80px+5px)] left-[calc(300px+5px+315px+5px)] z-50 overflow-y-auto w-68 rounded-md bg-white text-slate-800 flex flex-col gap-3 item-center pb-3 max-h-[calc(100vh-80px-10px)]"
>
  <div class="bg-primary p-3 rounded-b-none rounded-t-md text-white">
    <p>Prompt settings</p>
  </div>
  <div class="p-3 flex flex-col gap-2">
    <div class="flex items-center justify-between">
      <textarea
        placeholder="Enter your prompt here"
        class="p-2 border rounded-lg border-gray-200 outline-none text-slate-800 focus:border-primary resize-none overflow-hidden"
        bind:this={textarea}
        bind:value={current_content}
      />
    </div>
    <div class="flex flex-row gap-2 px-3 justify-center">
      <PrimaryButton on:click={handleOK} isSelected disabled={current_content === ""}>
        OK
      </PrimaryButton>
      <PrimaryButton on:click={handleCancel}>Cancel</PrimaryButton>
    </div>
  </div>
</div>
