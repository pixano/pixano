<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { AlignJustify, Sparkles } from "lucide-svelte";

  import { api, MultimodalImageNLPTask, PrimaryButton } from "@pixano/core";

  import AddModelModal from "./AddModelModal.svelte";
  import { connect } from "./connect";
  import ConnectModal from "./ConnectModal.svelte";

  export let selectedModel: string;
  let defaultURL = "http://localhost:9152";
  let isConnected = false;
  let models: { id: string; value: string }[] = [];

  $: if (!selectedModel && models.length >= 1) {
    selectedModel = models[0].value;
  }

  //Try to connect with default URL at startup
  connect(defaultURL)
    .then((status) => {
      isConnected = status;
      if (isConnected) listModels();
    })
    .catch(() => {});

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

  let showConnectModal = false;
  let showAddModelModal = false;

  const handleOpenConnectModal = (event: MouseEvent) => {
    // stopPropgation is not called as event modifier
    // because event modifiers can only be used on DOM elements
    event.stopPropagation();
    showConnectModal = true;
    document.body.addEventListener("click", handleCloseConnectModal);
  };

  const handleCloseConnectModal = () => {
    showConnectModal = false;
    document.body.removeEventListener("click", handleCloseConnectModal);
  };

  const handleOpenAddModelModal = (event: MouseEvent) => {
    // stopPropgation is not called as event modifier
    // because event modifiers can only be used on DOM elements
    event.stopPropagation();
    showAddModelModal = true;
    document.body.addEventListener("click", handleCloseAddModelModal);
  };

  const handleCloseAddModelModal = () => {
    showAddModelModal = false;
    document.body.removeEventListener("click", handleCloseAddModelModal);
  };

  const handleKeyDown = (
    event: KeyboardEvent & {
      currentTarget: EventTarget & Window;
    },
  ) => {
    if (event.key === "Escape") {
      if ((event.target as Element)?.tagName === "INPUT") return event.preventDefault();
      showConnectModal = false;
      showAddModelModal = false;
    }
  };
</script>

<div class="px-3 flex flex-row gap-2">
  <div class="flex-none content-center">
    <button
      on:click={handleOpenConnectModal}
      class="p-2 rounded-full hover:bg-primary-light transition duration-300"
    >
      <Sparkles
        size={20}
        class={`${isConnected ? (selectedModel && selectedModel !== "" ? "text-green-500" : "text-yellow-500") : "text-red-500"}`}
      />
    </button>
    {#if showConnectModal}
      <ConnectModal bind:isConnected {defaultURL} on:cancelConnect={handleCloseConnectModal} />
    {/if}
  </div>
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
    <PrimaryButton disabled={!isConnected} on:click={handleOpenAddModelModal}>
      <AlignJustify />
    </PrimaryButton>
    {#if showAddModelModal}
      <AddModelModal on:listModels={listModels} on:cancelAddModel={handleCloseAddModelModal} />
    {/if}
  </div>
</div>
<svelte:window on:keydown={handleKeyDown} />
