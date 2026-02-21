<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import * as api from "$lib/api";
  import {
    Input,
    LoadingModal,
    MultimodalImageNLPTask,
    PrimaryButton,
    type ModelConfig,
  } from "$lib/ui";

  interface Props {
    vqaSectionWidth: number;
    onCancelAddModel?: () => void;
    onListModels?: () => void;
  }

  let { vqaSectionWidth, onCancelAddModel, onListModels }: Props = $props();

  //TMP: default values
  const modelChoices = {
    "llava-qwen": {
      provider: "vllm",
      model_name: "llava-qwen",
      model_path: "llava-hf/llava-onevision-qwen2-0.5b-ov-hf",
      dtype: "float16",
    },
    "llava-mistral": {
      provider: "vllm",
      model_name: "llava-mistral",
      model_path: "llava-hf/llava-v1.6-mistral-7b-hf",
      dtype: "float16",
    },
    spatialRGPT: {
      provider: "transformers",
      model_name: "spatialRGPT",
      model_path: "a8cheng/SpatialRGPT-VILA1.5-8B",
      dtype: "float16",
    },
  };
  let formData = $state(modelChoices["llava-qwen"]);

  let isAddingModelRequestPending = $state(false);

  function handleCancel() {
    onCancelAddModel?.();
  }

  const handleChange = (event: Event & { currentTarget: EventTarget & HTMLInputElement }) => {
    const { name, value } = event.currentTarget;
    formData = { ...formData, [name]: value };
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

    onListModels?.();
    onCancelAddModel?.();
  };
</script>

<!-- stop propagation to prevent from closing the modal when clicking on the background -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  onclick={(event) => event.stopPropagation()}
  class="fixed top-[calc(80px+5px)] z-50 overflow-y-auto w-68 rounded-md bg-card text-foreground flex flex-col gap-3 item-center pb-3 max-h-[calc(100vh-80px-10px)]"
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
      onchange={handleChange}
      onkeyup={(e) => e.stopPropagation()}
    />
    <h5 class="font-medium">Name</h5>
    <Input
      name="model_name"
      value={formData.model_name}
      type="string"
      onchange={handleChange}
      onkeyup={(e) => e.stopPropagation()}
    />
    <h5 class="font-medium">Path</h5>
    <Input
      name="model_path"
      value={formData.model_path}
      type="string"
      onchange={handleChange}
      onkeyup={(e) => e.stopPropagation()}
    />
    <h5 class="font-medium">Data Type (advanced users)</h5>
    <Input
      name="dtype"
      value={formData.dtype}
      type="string"
      onchange={handleChange}
      onkeyup={(e) => e.stopPropagation()}
    />
  </div>
  <div class="flex flex-row gap-2 px-3 justify-center">
    <PrimaryButton onclick={handleCancel}>Cancel</PrimaryButton>
    <PrimaryButton
      onclick={handleAddModel}
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
