<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { createEventDispatcher } from "svelte";

  import { PrimaryButton, QuestionTypeEnum } from "@pixano/core";
  import { AutoResizeTextarea } from "@pixano/core/src/components/ui/autoresize-textarea";

  import { completionModelsStore } from "../../../stores/completionModels";

  export let vqaSectionWidth: number;

  let question_type = QuestionTypeEnum.OPEN; //TODO selector to choose question type
  let message_type: "question" | "answer" = "question";

  let completionPrompt =
    $completionModelsStore.find((m) => m.selected)?.prompts[message_type][question_type] ?? null;

  let newPromptContent = completionPrompt ?? "";

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
                  [question_type]: newPromptContent,
                },
              },
            }
          : model,
      ),
    );

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
    <AutoResizeTextarea placeholder="Enter your prompt here" bind:value={newPromptContent} />

    <div class="flex flex-row gap-2 px-3 justify-center">
      <PrimaryButton on:click={handleCancel}>Cancel</PrimaryButton>
      <PrimaryButton on:click={handleSavePrompt} isSelected disabled={newPromptContent === ""}>
        Save
      </PrimaryButton>
    </div>
  </div>
</div>
