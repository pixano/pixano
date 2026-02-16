<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Cpu, Settings } from "lucide-svelte";

  import { IconButton } from "@pixano/core";
  import { inferenceServerStore, vqaModels } from "@pixano/core/src/lib/stores/inferenceStore";

  import { completionModelsStore } from "../../../stores/completionModels";
  import ConfigurePromptModal from "../../manageModels/components/ConfigurePromptModal.svelte";

  export let vqaSectionWidth: number;

  let selectedModel: string;
  let showPromptModal = false;

  $: inferenceModels = $vqaModels.map((m) => ({ id: m.name, value: m.name }));

  $: if (selectedModel) {
    completionModelsStore.update((models) =>
      models.map((model) =>
        model.name === selectedModel ? { ...model, selected: true } : { ...model, selected: false },
      ),
    );
  }

  $: if (!selectedModel && inferenceModels.length >= 1) {
    selectedModel = inferenceModels[0].id;
  }
</script>

<div class="h-16 px-4 border-b bg-card flex items-center justify-between shadow-sm z-10 shrink-0">
  <div class="flex items-center gap-3 overflow-hidden grow">
    <div class="p-2 bg-primary/10 rounded-lg text-primary shrink-0">
      <Cpu size={20} />
    </div>

    {#if !$inferenceServerStore.connected}
      <span class="text-sm font-medium text-muted-foreground truncate">Server disconnected</span>
    {:else if inferenceModels.length === 0}
      <span class="text-sm font-medium text-muted-foreground truncate">No VLM models</span>
    {:else}
      <select
        class="bg-transparent border-none outline-none text-sm font-semibold text-foreground cursor-pointer truncate grow"
        bind:value={selectedModel}
      >
        {#each inferenceModels as { id, value }}
          <option value={id}>{value}</option>
        {/each}
      </select>
    {/if}
  </div>

  <div class="flex items-center gap-1">
    <IconButton
      tooltipContent="Model & Prompt Settings"
      disabled={$completionModelsStore.length === 0}
      on:click={() => (showPromptModal = !showPromptModal)}
    >
      <Settings size={20} />
    </IconButton>
  </div>
</div>

{#if showPromptModal}
  <ConfigurePromptModal {vqaSectionWidth} on:cancelPrompt={() => (showPromptModal = false)} />
{/if}
