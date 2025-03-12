<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { createEventDispatcher } from "svelte";

  import {
    api,
    Input,
    LoadingModal,
    MultimodalImageNLPTask,
    PrimaryButton,
    type InputEvents,
    type ModelConfig,
  } from "@pixano/core";

  export let vqaSectionWidth: number;

  //default values
  let formData = {
    provider: "vllm",
    model_name: "llava-qwen",
    model_path: "llava-hf/llava-onevision-qwen2-0.5b-ov-hf",
    dtype: "float16",
  };

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
        task: MultimodalImageNLPTask.CONDITIONAL_GENERATION,
        path: formData.model_path,
        config: { dtype: formData.dtype },
        processor_config: {},
      },
      provider: formData.provider,
    };

    const success = await api.instantiateModel(model_config); //NOTE: take some time (~40sec)

    if (!success) {
      console.error(`Couldn't instantiate model '${model_config.config.name}'`);
      return;
    }

    isAddingModelRequestPending = false;
    console.log(`Model '${model_config.config.name}' added.`);

    dispatch("listModels");
    dispatch("cancelAddModel");
  };
</script>

<!-- stop propagation to prevent from closing the modal when clicking on the background -->
<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div
  on:click|stopPropagation={() => {}}
  class="fixed top-[calc(80px+5px)] z-50 overflow-y-auto w-68 rounded-md bg-white text-slate-800 flex flex-col gap-3 item-center pb-3 max-h-[calc(100vh-80px-10px)]"
  style={`left: calc(${vqaSectionWidth}px + 10px);`}
>
  <div class="bg-primary p-3 rounded-b-none rounded-t-md text-white">
    <p>Instantiate VQA model</p>
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
