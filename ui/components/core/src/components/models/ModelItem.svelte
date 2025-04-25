<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Settings, Trash2 } from "lucide-svelte";
  import { createEventDispatcher } from "svelte";

  import { api, IconButton, MultimodalImageNLPTask, type Task } from "../..";
  import { pixanoInferenceModelsStore } from "../../lib/types/inference/modelsStore";

  export let modelName: string;
  export let task: Task;

  const dispatch = createEventDispatcher();

  const handleDeleteModel = () => {
    api.deleteModel(modelName).then(() => {
      pixanoInferenceModelsStore.update((models) =>
        models.filter((m) => !(m.name === modelName && m.task === task)),
      );
    });
  };
  const handleOpenPromptModal = () => {
    dispatch("promptModal", modelName);
  };
</script>

<div class="border rounded p-3 flex items-center justify-between gap-2 hover:bg-gray-50">
  <label class="flex items-center gap-2 cursor-pointer flex-grow">
    <input
      type="radio"
      name="model-selection"
      bind:group={modelName}
      value={modelName}
      on:change={() => dispatch("select")}
    />
    <span>{modelName}</span>
  </label>

  {#if task === MultimodalImageNLPTask.CONDITIONAL_GENERATION}
    <IconButton
      tooltipContent="Configure generation prompts and temperature"
      on:click={handleOpenPromptModal}
    >
      <Settings />
    </IconButton>
  {/if}
  <IconButton tooltipContent="Delete model" on:click={handleDeleteModel}>
    <Trash2 />
  </IconButton>
</div>
