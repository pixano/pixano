<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Trash2 } from "lucide-svelte";
  import { createEventDispatcher } from "svelte";

  import { api, IconButton } from "../..";
  import { pixanoInferenceSegmentationModelsStore } from "./inference";

  export let modelName: string;

  const dispatch = createEventDispatcher();

  const handleDeleteModel = () => {
    api
      .deleteModel(modelName)
      .then(() => {
        pixanoInferenceSegmentationModelsStore.update((models) =>
          models.filter((m) => m.name !== modelName),
        );
      })
      .catch((err) => console.error("ERROR: Could not delete model.", err));
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

  <IconButton tooltipContent="Delete model" on:click={handleDeleteModel}>
    <Trash2 />
  </IconButton>
</div>
