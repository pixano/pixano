<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Plus } from "lucide-svelte";
  import { createEventDispatcher } from "svelte";

  import { PrimaryButton, type Task } from "../..";
  import {
    pixanoInferenceModelsStore,
    type PixanoInferenceModel,
  } from "../../lib/types/inference/modelsStore";
  import AddModelModal from "./AddModelModal.svelte";
  import ConfigurePromptModal from "./ConfigurePromptModal.svelte";
  import ModelItem from "./ModelItem.svelte";

  export let task: Task;
  export let listModels: () => void;

  let showPromptModal = false;
  let promptModelName: string;

  const dispatch = createEventDispatcher();

  let showAddModelModal = false;
  let models: PixanoInferenceModel[] = [];

  pixanoInferenceModelsStore.subscribe((ms) => {
    models = ms.filter((m) => m.task === task);
  });

  const handleSelect = (selectedModelName: string) => {
    pixanoInferenceModelsStore.update((models) =>
      models.map((m) => {
        if (m.task === task) {
          m.selected = m.name === selectedModelName;
        }
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

  const handleOpenPromptModal = (modelName: string) => {
    if (showPromptModal) {
      handleClosePromptModal();
    } else {
      showPromptModal = true;
      promptModelName = modelName;
    }
  };
  const handleClosePromptModal = () => {
    showPromptModal = false;
  };

  function handleCancel() {
    dispatch("cancel");
  }
</script>

<!-- stop propagation to prevent from closing the modal when clicking on the background -->
<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div
  on:click|stopPropagation={() => {}}
  class="fixed top-[calc(80px+5px)] left-1/2 transform -translate-x-1/2 z-50 overflow-y-auto w-68 rounded-md bg-white text-slate-800 flex flex-col gap-3 item-center pb-3 max-h-[calc(100vh-80px-10px)]"
>
  <div class="bg-primary p-3 rounded-b-none rounded-t-md text-white">
    <p>Select a Mask Generation Model</p>
  </div>
  <div class="p-3 flex flex-col gap-2">
    {#if models.length === 0}
      <p class="text-gray-500">No models added yet.</p>
    {/if}

    <div class="flex flex-col gap-2 max-h-[300px] overflow-y-auto">
      {#each models as model}
        <ModelItem
          modelName={model.name}
          task={model.task}
          on:select={() => handleSelect(model.name)}
          on:promptModal={(event) => handleOpenPromptModal(event.detail)}
        />
      {/each}
    </div>
    <PrimaryButton on:click={handleOpenAddModelModal}>
      <Plus />Add a model
    </PrimaryButton>
  </div>
  <div class="flex flex-row gap-2 px-3 justify-center">
    <PrimaryButton on:click={handleCancel}>Cancel</PrimaryButton>
    <PrimaryButton on:click={handleCancel}>OK</PrimaryButton>
  </div>
</div>

{#if showAddModelModal}
  <AddModelModal {task} on:listModels={listModels} on:cancelAddModel={handleCloseAddModelModal} />
{/if}
{#if showPromptModal}
  <ConfigurePromptModal modelName={promptModelName} on:cancelPrompt={handleClosePromptModal} />
{/if}
