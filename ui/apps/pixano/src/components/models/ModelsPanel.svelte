<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { RefreshCw, Server, Sparkles } from "lucide-svelte";

  import { ConnectToServerModal, IconButton, PrimaryButton } from "@pixano/core";
  import { refreshInferenceModels } from "@pixano/core/src/lib/services/inferenceService";
  import {
    inferenceServerStore,
    type InferenceModel,
  } from "@pixano/core/src/lib/stores/inferenceStore";

  let showConnectModal = false;

  type ModelGroup = { label: string; models: InferenceModel[] };

  function groupModelsByTask(models: InferenceModel[]): ModelGroup[] {
    const groups: Record<string, InferenceModel[]> = {};
    for (const model of models) {
      const label = formatTaskLabel(model.task);
      if (!groups[label]) groups[label] = [];
      groups[label].push(model);
    }
    return Object.entries(groups).map(([label, models]) => ({ label, models }));
  }

  function formatTaskLabel(task: string): string {
    return task.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }

  $: modelGroups = groupModelsByTask($inferenceServerStore.models);
</script>

<div class="flex flex-col h-full bg-muted/30 p-5 gap-4">
  <div class="flex items-center justify-between">
    <div class="flex items-center gap-2">
      <Sparkles size={18} class="text-muted-foreground" />
      <h2 class="text-sm font-semibold text-foreground uppercase tracking-wide">Inference</h2>
    </div>
    <div class="flex items-center gap-1">
      {#if $inferenceServerStore.connected}
        <IconButton tooltipContent="Refresh models" on:click={() => refreshInferenceModels()}>
          <RefreshCw size={16} />
        </IconButton>
      {/if}
    </div>
  </div>

  <div class="flex items-center gap-2">
    <div
      class="h-2 w-2 rounded-full {$inferenceServerStore.connected ? 'bg-green-500' : 'bg-red-400'}"
    ></div>
    <span class="text-sm text-muted-foreground">
      {#if $inferenceServerStore.connected}
        Connected to <span class="text-foreground font-medium">{$inferenceServerStore.url}</span>
      {:else}
        Not connected
      {/if}
    </span>
  </div>

  {#if !$inferenceServerStore.connected}
    <div class="flex flex-col items-center gap-3 py-4 text-center">
      <Server size={32} class="text-muted-foreground/50" />
      <p class="text-sm text-muted-foreground">
        Connect to an inference server to use AI models for annotation.
      </p>
      <PrimaryButton on:click={() => (showConnectModal = true)} isSelected>Connect</PrimaryButton>
    </div>
  {:else if $inferenceServerStore.models.length === 0}
    <div class="flex flex-col items-center gap-2 py-4 text-center">
      <p class="text-sm text-muted-foreground">
        Connected, but no models are deployed on this server.
      </p>
    </div>
  {:else}
    <div class="flex flex-col gap-3 flex-1 min-h-0 overflow-y-auto">
      {#each modelGroups as group}
        <div class="flex flex-col gap-1.5">
          <span class="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            {group.label}
          </span>
          {#each group.models as model}
            <div
              class="flex items-center gap-2 px-2 py-1.5 rounded-md bg-background border border-border/50"
            >
              <span class="text-sm text-foreground truncate">{model.name}</span>
            </div>
          {/each}
        </div>
      {/each}
    </div>
  {/if}

  {#if $inferenceServerStore.connected}
    <button
      class="text-xs text-muted-foreground hover:text-foreground transition-colors text-left"
      on:click={() => (showConnectModal = true)}
    >
      Change server...
    </button>
  {/if}
</div>

{#if showConnectModal}
  <ConnectToServerModal
    defaultUrl={$inferenceServerStore.url ?? ""}
    on:close={() => (showConnectModal = false)}
    on:connected={() => (showConnectModal = false)}
  />
{/if}
