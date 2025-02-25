<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { AlignJustify } from "lucide-svelte";

  import { api, MultimodalImageNLPTask, PrimaryButton } from "@pixano/core";

  import AddModelModal from "./ConnectAddModelModal.svelte";

  export let selectedModel: string;
  let models: { id: string; value: string }[] = [];

  $: if (!selectedModel && models.length >= 1) {
    selectedModel = models[0].value;
  }

  const listModels = () => {
    api
      .listModels(MultimodalImageNLPTask.CONDITIONAL_GENERATION)
      .then((available_models) => {
        models = available_models.map((model) => {
          return { id: model.name, value: model.name };
        });
      })
      .catch((err) => console.error("Can't list models", err));
  };

  let showAddModelModal = false;

  const handleOpenModal = (event: MouseEvent) => {
    // stopPropgation is not called as event modifier
    // because event modifiers can only be used on DOM elements
    event.stopPropagation();
    showAddModelModal = true;
    document.body.addEventListener("click", handleCloseModal);
  };

  const handleCloseModal = () => {
    showAddModelModal = false;
    document.body.removeEventListener("click", handleCloseModal);
  };

  const handleKeyDown = (
    event: KeyboardEvent & {
      currentTarget: EventTarget & Window;
    },
  ) => {
    if (event.key === "Escape") {
      if ((event.target as Element)?.tagName === "INPUT") return event.preventDefault();
      showAddModelModal = false;
    }
  };
</script>

<div class="px-3 flex flex-row gap-2">
  <div class="flex flex-col grow">
    <!-- For some reason, some tailwind classes don't work on select -->
    <!-- Use style instead -->
    <select
      class="py-3 px-2 border rounded-lg border-gray-200 outline-none text-slate-800"
      style="color: #1e293b; border-color: #e5e7eb;"
      bind:value={selectedModel}
    >
      <option value="" selected disabled>Select a model</option>
      {#each models as { id, value }}
        <option value={id}>{value}</option>
      {/each}
    </select>
  </div>
  <div class="flex-none content-center">
    <PrimaryButton on:click={handleOpenModal}><AlignJustify /></PrimaryButton>
    {#if showAddModelModal}
      <AddModelModal on:listModels={listModels} on:cancel={handleCloseModal} />
    {/if}
  </div>
</div>
<svelte:window on:keydown={handleKeyDown} />
