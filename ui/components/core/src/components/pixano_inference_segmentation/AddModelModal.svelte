<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { createEventDispatcher } from "svelte";

  import {
    api,
    ImageTask,
    Input,
    LoadingModal,
    PrimaryButton,
    VideoTask,
    type InputEvents,
    type ModelConfig,
  } from "../..";

  export let isVideo: boolean = false;

  //TMP: default values
  const modelChoices = {
    sam2: {
      provider: "sam2",
      model_name: "SAM2" + (isVideo ? "_video" : ""),
      model_path: "facebook/sam2-hiera-tiny",
      dtype: "float32",
    },
  };
  let formData = modelChoices["sam2"];

  let isAddingModelRequestPending = false;
  const dispatch = createEventDispatcher();

  function handleCancel() {
    dispatch("cancelAddModel");
  }

  const handleChange = (event: InputEvents["change"]) => {
    if (event.target && "name" in event.target && "value" in event.target) {
      const name: string = event.target.name as string;
      const value: string = event.target.value as string;
      formData = { ...formData, [name]: value };
    }
  };

  const handleAddModel = async () => {
    isAddingModelRequestPending = true;
    const model_config: ModelConfig = {
      config: {
        name: formData.model_name,
        task: isVideo ? VideoTask.MASK_GENERATION : ImageTask.MASK_GENERATION,
        path: formData.model_path,
        // Note: dtype or torch_dtype ? >> some model requires dtype, others torch_dtype, so use both
        config: { dtype: formData.dtype, torch_dtype: formData.dtype },
        processor_config: {},
      },
      provider: formData.provider,
    };
    const success = await api.instantiateModel(model_config); //NOTE: may take some time
    if (!success) {
      console.error(`Couldn't instantiate model '${model_config.config.name}'`);
      return;
    } else {
      console.log(`Model '${model_config.config.name}' added.`);
    }

    isAddingModelRequestPending = false;

    dispatch("listModels");
    dispatch("cancelAddModel");
  };
</script>

<!-- stop propagation to prevent from closing the modal when clicking on the background -->
<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div
  on:click|stopPropagation={() => {}}
  class="fixed top-[calc(80px+5px)] left-1/2 transform -translate-x-1/2 z-50 overflow-y-auto w-68 rounded-md bg-white text-slate-800 flex flex-col gap-3 item-center pb-3 max-h-[calc(100vh-80px-10px)]"
>
  <div class="bg-primary p-3 rounded-b-none rounded-t-md text-white">
    <p>Instantiate Segmentation model {isVideo ? " for Video" : ""}</p>
  </div>
  <div class="p-3 flex flex-col gap-2">
    <h5 class="font-medium">Provider (only use providers installed with pixano-inference)</h5>
    <Input
      name="provider"
      value={formData.provider}
      type="string"
      on:change={handleChange}
      on:keyup={(e) => e.stopPropagation()}
    />
    <h5 class="font-medium">Name</h5>
    <Input
      name="model_name"
      value={formData.model_name}
      type="string"
      on:change={handleChange}
      on:keyup={(e) => e.stopPropagation()}
    />
    <h5 class="font-medium">Path</h5>
    <Input
      name="model_path"
      value={formData.model_path}
      type="string"
      on:change={handleChange}
      on:keyup={(e) => e.stopPropagation()}
    />
    <h5 class="font-medium">Data Type (advanced users)</h5>
    <Input
      name="dtype"
      value={formData.dtype}
      type="string"
      on:change={handleChange}
      on:keyup={(e) => e.stopPropagation()}
    />
  </div>
  <div class="flex flex-row gap-2 px-3 justify-center">
    <PrimaryButton on:click={handleCancel}>Cancel</PrimaryButton>
    <PrimaryButton
      on:click={handleAddModel}
      isSelected
      disabled={isAddingModelRequestPending || Object.values(formData).some((v) => v === "")}
    >
      Add Model
    </PrimaryButton>
  </div>
</div>

{#if isAddingModelRequestPending}
  <LoadingModal />
{/if}
