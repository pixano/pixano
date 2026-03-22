<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { ArrowsClockwise, HardDrives, Plus, Sparkle } from "phosphor-svelte";

  import ConnectToServerModal from "./ConnectToServerModal.svelte";
  import {
    ensureInferenceRegistryLoaded,
    refreshInferenceModels,
  } from "$lib/services/inferenceService";
  import { inferenceServerStore } from "$lib/stores/inferenceStores.svelte";
  import { formatInferenceProviderName, type InferenceModel } from "$lib/types/inference";
  import { IconButton, PrimaryButton } from "$lib/ui";

  let showConnectModal = $state(false);

  type ModelGroup = { label: string; models: InferenceModel[] };

  function groupModelsByTask(models: InferenceModel[]): ModelGroup[] {
    const groups: Record<string, InferenceModel[]> = {};
    for (const model of models) {
      const label = formatTaskLabel(model.task);
      if (!groups[label]) groups[label] = [];
      groups[label].push(model);
    }
    return Object.entries(groups).map(([label, groupModels]) => ({ label, models: groupModels }));
  }

  function formatTaskLabel(task: string): string {
    return task.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }

  const modelGroups = $derived(groupModelsByTask(inferenceServerStore.value.models));

  $effect(() => {
    void ensureInferenceRegistryLoaded();
  });
</script>

<div class="flex flex-col h-full bg-card p-6 gap-6">
  <div class="flex items-center justify-between border-b border-border/50 pb-4">
    <div class="flex items-center gap-2.5">
      <div class="p-2 rounded-lg bg-primary/5">
        <Sparkle weight="regular" size={22} class="text-primary" />
      </div>
      <h2 class="text-xs font-bold text-foreground uppercase tracking-[0.1em]">Inference</h2>
    </div>
    {#if inferenceServerStore.value.connected}
      <IconButton
        tooltipContent="Refresh servers and models"
        onclick={() => void refreshInferenceModels()}
        class="h-8 w-8"
      >
        <ArrowsClockwise weight="regular" size={18} />
      </IconButton>
    {/if}
  </div>

  <div class="space-y-3">
    <h3
      class="text-[10px] font-bold text-muted-foreground uppercase tracking-widest px-1 opacity-60"
    >
      Servers
    </h3>
    {#if inferenceServerStore.value.providers.length > 0}
      <div class="flex flex-col gap-2">
        {#each inferenceServerStore.value.providers as provider}
          <div
            class="group flex items-center gap-3 p-2.5 rounded-xl bg-muted/30 border border-border/50 transition-all duration-200 hover:border-primary/20"
          >
            <div
              class="h-2 w-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.4)] shrink-0"
            ></div>
            <div class="min-w-0 flex-1">
              <p class="text-[13px] text-foreground font-semibold truncate">
                {provider.url ?? provider.name}
              </p>
              <p class="text-[10px] text-muted-foreground truncate">
                {provider.name === inferenceServerStore.value.defaultProvider
                  ? "Default server"
                  : provider.name}
              </p>
            </div>
          </div>
        {/each}
      </div>
    {:else}
      <div
        class="flex items-center gap-3 p-2.5 rounded-xl bg-muted/20 border border-dashed border-border/60"
      >
        <div class="h-2 w-2 rounded-full bg-muted-foreground/30 shrink-0"></div>
        <span class="text-[13px] text-muted-foreground font-medium italic">
          Offline — No server
        </span>
      </div>
    {/if}
  </div>

  {#if !inferenceServerStore.value.connected}
    <div
      class="flex flex-col items-center gap-4 py-8 text-center bg-muted/20 rounded-2xl border border-border/40 mt-2 px-4"
    >
      <div
        class="w-12 h-12 rounded-full bg-background flex items-center justify-center shadow-sm border border-border/50"
      >
        <HardDrives weight="regular" size={28} class="text-muted-foreground/40" />
      </div>
      <div class="space-y-1.5">
        <p class="text-sm font-bold text-foreground">No server connected</p>
        <p class="text-[12px] text-muted-foreground leading-relaxed px-2">
          Connect one or more inference servers to enable AI-powered annotation tools.
        </p>
      </div>
      <PrimaryButton onclick={() => (showConnectModal = true)}>Connect Server</PrimaryButton>
    </div>
  {:else if inferenceServerStore.value.models.length === 0}
    <div
      class="flex flex-col items-center gap-2 py-8 text-center bg-muted/10 rounded-2xl border border-dashed border-border mt-2"
    >
      <p class="text-[13px] text-muted-foreground font-medium px-6">
        Connected, but no deployed models were reported by the registered servers.
      </p>
    </div>
  {:else}
    <div class="flex flex-col gap-6 flex-1 min-h-0 overflow-y-auto pr-1">
      {#each modelGroups as group}
        <div class="flex flex-col gap-3">
          <span
            class="text-[10px] font-black text-muted-foreground uppercase tracking-[0.15em] px-1 opacity-60"
          >
            {group.label}
          </span>
          <div class="grid gap-2">
            {#each group.models as model}
              <div
                class="flex flex-col gap-0.5 px-3.5 py-3 rounded-xl bg-background border border-border/60 shadow-sm transition-all duration-200 hover:border-primary/30 hover:shadow-md group/model"
              >
                <span
                  class="text-[13px] font-bold text-foreground truncate group-hover/model:text-primary transition-colors"
                >
                  {model.name}
                </span>
                <span
                  class="text-[10px] text-muted-foreground font-medium flex items-center gap-1.5"
                >
                  <span class="opacity-50 italic">Provider:</span>
                  {formatInferenceProviderName(model.provider_name)}
                </span>
              </div>
            {/each}
          </div>
        </div>
      {/each}
    </div>
  {/if}

  {#if inferenceServerStore.value.connected}
    <button
      class="flex items-center gap-2 text-[12px] text-muted-foreground hover:text-primary font-medium transition-colors px-1 mt-auto"
      onclick={() => (showConnectModal = true)}
    >
      <Plus weight="bold" size={14} />
      Add another server
    </button>
  {/if}
</div>

{#if showConnectModal}
  <ConnectToServerModal
    onClose={() => (showConnectModal = false)}
    onConnected={() => (showConnectModal = false)}
  />
{/if}
