<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Trash } from "phosphor-svelte";

  import * as api from "$lib/api";
  import { IconButton } from "$lib/ui";
  import { pixanoInferenceSegmentationModelsStore } from "$lib/stores/inferenceStores.svelte";

  interface Props {
    modelName: string;
    onSelect?: () => void;
  }

  let { modelName = $bindable(), onSelect }: Props = $props();

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

<div class="border rounded p-3 flex items-center justify-between gap-2 hover:bg-accent">
  <label class="flex items-center gap-2 cursor-pointer flex-grow">
    <input
      type="radio"
      name="model-selection"
      bind:group={modelName}
      value={modelName}
      onchange={onSelect}
    />
    <span>{modelName}</span>
  </label>

  <IconButton tooltipContent="Delete model" onclick={handleDeleteModel}>
    <Trash weight="regular" />
  </IconButton>
</div>
