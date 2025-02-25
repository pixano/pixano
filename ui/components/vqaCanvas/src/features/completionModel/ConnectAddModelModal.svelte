<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { createEventDispatcher } from "svelte";

  import {
    api,
    LoadingModal,
    MultimodalImageNLPTask,
    PrimaryButton,
    type ModelConfig,
  } from "@pixano/core";
  import type { InputEvents } from "@pixano/core/src/components/ui/input";
  import Input from "@pixano/core/src/components/ui/input/input.svelte";

  //TMP: default values
  let formData = {
    pi_url: "http://localhost:9152",
    provider: "vllm",
    model_name: "llava-qwen",
    model_path: "llava-hf/llava-onevision-qwen2-0.5b-ov-hf",
    dtype: "bfloat16",
  };

  let isWorking = false;

  const dispatch = createEventDispatcher();

  function handleConnect() {
    api
      .inferenceConnect(formData.pi_url)
      .then(() => {
        console.log("connected to Pixano Inference at:", formData.pi_url);
        dispatch("listModels");
        dispatch("cancel"); //also close modal (?)
      })
      .catch(() => {
        console.error("NOT connected to Pixano Inference!");
      });
  }

  function handleCancel() {
    dispatch("cancel");
  }

  const handleChange = (event: InputEvents["change"]) => {
    if (event.target && "name" in event.target && "value" in event.target) {
      const name: string = event.target.name as string;
      const value: string = event.target.value as string;
      formData = { ...formData, [name]: value };
    }
  };

  const handleAddModel = () => {
    isWorking = true;
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
    console.log("XXX Model config:", model_config);
    api
      .instantiateModel(model_config) //NOTE: take some time (~40sec)
      .then(() => {
        isWorking = false;
        console.log(`Model '${model_config.config.name}' added.`);
        dispatch("listModels");
      })
      .catch((err) => {
        isWorking = false;
        console.error(`Couldn't instantiate model '${model_config.config.name}'`, err);
        //TMP BUG: even if OK, I got a 500 Internal Server Error ... so refresh model list anyway
        dispatch("listModels");
        dispatch("cancel");
      });
  };
</script>

<!-- stop propagation to prevent from closing the modal when clicking on the background -->
<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div
  on:click|stopPropagation={() => {}}
  class="fixed top-[calc(80px+5px)] left-[calc(300px+5px+315px+5px)] z-50 overflow-y-auto w-68 rounded-md bg-white text-slate-800 flex flex-col gap-3 item-center pb-3 max-h-[calc(100vh-80px-10px)]"
>
  <div class="bg-primary p-3 rounded-b-none rounded-t-md text-white">
    <p>Pixano Inference connection</p>
  </div>
  <div class="flex flex-col">
    <h5 class="font-medium">Pixano Inference provider URL</h5>
    <div class="flex flex-row gap-2 px-3">
      <Input
        name="pi_url"
        value={formData.pi_url}
        type="string"
        on:change={handleChange}
        on:keyup={(e) => e.stopPropagation()}
      />
      <PrimaryButton
        on:click={handleConnect}
        isSelected
        disabled={isWorking || formData.pi_url === ""}
      >
        OK
      </PrimaryButton>
    </div>
  </div>
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
    <PrimaryButton
      on:click={handleAddModel}
      isSelected
      disabled={isWorking ||
        formData.provider === "" ||
        formData.model_name === "" ||
        formData.model_path === "" ||
        formData.dtype === ""}
    >
      Add Model
    </PrimaryButton>
    <PrimaryButton on:click={handleCancel}>Cancel</PrimaryButton>
  </div>
  {#if isWorking}
    <LoadingModal />
  {/if}
</div>
