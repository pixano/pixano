<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Plus, Sparkles } from "lucide-svelte";
  import { createEventDispatcher, onMount } from "svelte";

  import { api, IconButton, ImageTask, PrimaryButton } from "../..";
  import { isLocalSegmentationModel } from "../../../../../apps/pixano/src/lib/stores/datasetStores";
  import AddModelModal from "./AddModelModal.svelte";
  import ConnectModal from "./ConnectModal.svelte";
  import {
    pixanoInferenceSegmentationModelsStore,
    pixanoInferenceSegmentationURL,
    type PixanoInferenceSegmentationModel,
  } from "./inference";
  import ModelItem from "./ModelItem.svelte";

  const dispatch = createEventDispatcher();

  // Exports
  export let choices: Array<string>;
  export let selected: string;
  let localOrPixinf = $isLocalSegmentationModel ? "local" : "pixinf";

  let showAddModelModal = false;
  let showConnectModal = false;

  let isInferenceApiConnected = false;
  async function connectToPixanoInference() {
    isInferenceApiConnected = await api.isInferenceApiHealthy($pixanoInferenceSegmentationURL);
    if (isInferenceApiConnected) {
      await listModels();
    }
  }

  //Try to connect with default URL at startup
  onMount(connectToPixanoInference);

  const listModels = async () => {
    const availableSegmentationModels = await api.listModels(ImageTask.MASK_GENERATION);

    const availableSegmentationModelsNames = availableSegmentationModels.map((model) => model.name);

    //inferenceModels = availableSegmentationModels.map((name) => ({ id: name, value: name }));
    pixanoInferenceSegmentationModelsStore.update((currentList) =>
      mergeModelLists(availableSegmentationModelsNames, currentList),
    );
  };

  export function mergeModelLists(
    newModelsName: string[],
    existingModels: PixanoInferenceSegmentationModel[],
  ): PixanoInferenceSegmentationModel[] {
    const existingModelsMap = new Map(existingModels.map((model) => [model.name, model]));

    return newModelsName.map(
      (model) =>
        existingModelsMap.get(model) ?? {
          name: model,
          selected: false,
        },
    );
  }

  const handleSelect = (selectedModelName: string) => {
    pixanoInferenceSegmentationModelsStore.update((models) =>
      models.map((m) => {
        m.selected = m.name === selectedModelName;
        return m;
      }),
    );
  };
  const handleOpenAddModelModal = (event: Event) => {
    // stopPropgation is not called as event modifier
    // because event modifiers can only be used on DOM elements
    event.stopPropagation();
    if (showAddModelModal) {
      handleCloseAddModelModal();
    } else {
      showAddModelModal = true;
    }
  };
  const handleCloseAddModelModal = () => {
    showAddModelModal = false;
  };

  const handleLocalOrPixinfChange = () => {
    isLocalSegmentationModel.set(localOrPixinf === "local");
  };

  function handleConfirm() {
    dispatch("confirm");
  }

  function handleCancel() {
    dispatch("cancel");
  }
</script>

<!-- stop propagation to prevent from closing the modal when clicking on the background -->
<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div
  on:click|stopPropagation={() => {}}
  class="fixed top-[calc(80px+5px)] left-1/2 transform -translate-x-1/2 z-50
  rounded-md bg-white text-slate-800 flex flex-col gap-3 item-center pb-3 max-h-[calc(100vh-80px-10px)]"
>
  <div class="bg-primary p-3 rounded-b-none rounded-t-md text-white">
    <p>Select a Mask Generation Model</p>
  </div>
  <div class="flex flex-col p-3 gap-5">
    <label>
      <div class="flex flex-row gap-2">
        <input
          type="radio"
          bind:group={localOrPixinf}
          value="local"
          on:change={handleLocalOrPixinfChange}
        />
        <div class="flex flex-col gap-2">
          <p class="self-center">Local</p>
          {#if choices}
            <select
              class="py-1 px-2 border rounded focus:outline-none bg-slate-100 border-slate-300 focus:border-main"
              bind:value={selected}
            >
              {#each choices as choice}
                <option value={choice}>
                  {choice}
                </option>
              {/each}
            </select>
          {:else}
            <p class="pb-1 italic">No local model found</p>
          {/if}
        </div>
      </div>
    </label>
    <div class="h-1 bg-primary-light" />
    <label>
      <div class="flex flex-row gap-2">
        <input
          type="radio"
          bind:group={localOrPixinf}
          value="pixinf"
          on:change={handleLocalOrPixinfChange}
        />
        <div class="flex flex-col gap-2">
          <div class="flex flex-row">
            <IconButton
              tooltipContent="Pixano Inference connection"
              on:click={() => (showConnectModal = !showConnectModal)}
            >
              <Sparkles
                size={20}
                class={isInferenceApiConnected
                  ? $pixanoInferenceSegmentationModelsStore.length > 0
                    ? "text-green-500"
                    : "text-yellow-500"
                  : "text-red-500"}
              />
            </IconButton>
            <p class="self-center">Pixano Inference</p>
          </div>
          <div class="p-3 flex flex-col gap-2">
            {#if $pixanoInferenceSegmentationModelsStore.length === 0}
              <p class="text-gray-500">No models added yet.</p>
            {/if}

            <div class="flex flex-col gap-2 max-h-[300px] overflow-y-auto">
              {#each $pixanoInferenceSegmentationModelsStore as model}
                <ModelItem modelName={model.name} on:select={() => handleSelect(model.name)} />
              {/each}
            </div>
            <PrimaryButton on:click={handleOpenAddModelModal}>
              <Plus />Add a model
            </PrimaryButton>
          </div>
        </div>
      </div>
    </label>
    <div class="h-1 bg-primary-light" />
    <div class="flex flex-row gap-2 px-3 justify-center">
      <PrimaryButton on:click={handleCancel}>Cancel</PrimaryButton>
      <PrimaryButton on:click={handleConfirm}>OK</PrimaryButton>
    </div>
  </div>
</div>

{#if showConnectModal}
  <ConnectModal
    bind:isConnected={isInferenceApiConnected}
    on:cancelConnect={() => (showConnectModal = false)}
    on:listModels={listModels}
  />
{/if}

{#if showAddModelModal}
  <AddModelModal on:listModels={listModels} on:cancelAddModel={handleCloseAddModelModal} />
{/if}
