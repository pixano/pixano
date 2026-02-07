<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { RefreshCw, Server, Sparkles, X } from "lucide-svelte";

  import { ConnectToServerModal, IconButton, PrimaryButton } from "@pixano/core";
  import {
    disconnectFromProvider,
    refreshInferenceModels,
  } from "@pixano/core";
  import {
    inferenceServerStore,
    type InferenceModel,
  } from "@pixano/core";

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

  function formatProviderName(name: string): string {
    // Extract the host:port portion from "pixano-inference@host:port"
    const atIndex = name.indexOf("@");
    return atIndex >= 0 ? name.substring(atIndex + 1) : name;
  }

  $: modelGroups = groupModelsByTask($inferenceServerStore.models);
</script>

<div class="flex flex-col h-full bg-card p-6 gap-6">
  <div class="flex items-center justify-between border-b border-border/50 pb-4">
    <div class="flex items-center gap-2.5">
      <div class="p-2 rounded-lg bg-primary/5">
        <Sparkles size={18} class="text-primary" />
      </div>
      <h2 class="text-xs font-bold text-foreground uppercase tracking-[0.1em]">Inference</h2>
    </div>
    <div class="flex items-center gap-1">
      {#if $inferenceServerStore.connected}
        <IconButton tooltipContent="Refresh models" on:click={() => void refreshInferenceModels()} class="h-8 w-8">
          <RefreshCw size={14} />
        </IconButton>
      {/if}
    </div>
  </div>

  <!-- Connection Status -->
  <div class="space-y-3">
    <h3 class="text-[10px] font-bold text-muted-foreground uppercase tracking-widest px-1 opacity-60">Status</h3>
    {#if $inferenceServerStore.providers.length > 0}
      <div class="flex flex-col gap-2">
        {#each $inferenceServerStore.providers as provider}
          <div class="group flex items-center gap-3 p-2.5 rounded-xl bg-muted/30 border border-border/50 transition-all duration-200 hover:border-primary/20">
            <div class="h-2 w-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.4)] shrink-0"></div>
            <span class="text-[13px] text-foreground font-semibold truncate flex-1">
              {provider.url ?? provider.name}
            </span>
            <button
              class="text-muted-foreground opacity-0 group-hover:opacity-100 hover:text-destructive transition-all shrink-0 p-1"
              on:click={() => void disconnectFromProvider(provider.name)}
              title="Disconnect"
            >
              <X size={14} />
            </button>
          </div>
        {/each}
      </div>
    {:else}
      <div class="flex items-center gap-3 p-2.5 rounded-xl bg-muted/20 border border-dashed border-border/60">
        <div class="h-2 w-2 rounded-full bg-muted-foreground/30 shrink-0"></div>
        <span class="text-[13px] text-muted-foreground font-medium italic">Offline — No server</span>
      </div>
    {/if}
  </div>

  {#if !$inferenceServerStore.connected}
    <div class="flex flex-col items-center gap-4 py-8 text-center bg-muted/20 rounded-2xl border border-border/40 mt-2 px-4">
      <div class="w-12 h-12 rounded-full bg-background flex items-center justify-center shadow-sm border border-border/50">
        <Server size={24} class="text-muted-foreground/40" />
      </div>
      <div class="space-y-1.5">
        <p class="text-sm font-bold text-foreground">Connect to server</p>
        <p class="text-[12px] text-muted-foreground leading-relaxed px-2">
          Add an inference server to enable AI-powered annotation tools.
        </p>
      </div>
      <PrimaryButton on:click={() => (showConnectModal = true)} isSelected class="w-full">
        Connect Server
      </PrimaryButton>
    </div>
  {:else if $inferenceServerStore.models.length === 0}
    <div class="flex flex-col items-center gap-2 py-8 text-center bg-muted/10 rounded-2xl border border-dashed border-border mt-2">
      <p class="text-[13px] text-muted-foreground font-medium px-6">
        Connected, but no models found on the server.
      </p>
    </div>
  {:else}
    <div class="flex flex-col gap-6 flex-1 min-h-0 overflow-y-auto pr-1">
      {#each modelGroups as group}
        <div class="flex flex-col gap-3">
          <span class="text-[10px] font-black text-muted-foreground uppercase tracking-[0.15em] px-1 opacity-60">
            {group.label}
          </span>
          <div class="grid gap-2">
            {#each group.models as model}
              <div
                class="flex flex-col gap-0.5 px-3.5 py-3 rounded-xl bg-background border border-border/60 shadow-sm transition-all duration-200 hover:border-primary/30 hover:shadow-md group/model"
              >
                <span class="text-[13px] font-bold text-foreground truncate group-hover/model:text-primary transition-colors">
                  {model.name}
                </span>
                <span class="text-[10px] text-muted-foreground font-medium flex items-center gap-1.5">
                  <span class="opacity-50 italic">Provider:</span>
                  {formatProviderName(model.provider_name)}
                </span>
              </div>
            {/each}
          </div>
        </div>
      {/each}
    </div>
  {/if}

  {#if $inferenceServerStore.connected}
    <button
      class="mt-auto group flex items-center gap-2 py-3 px-1 text-[11px] font-bold text-muted-foreground hover:text-primary transition-all duration-200 uppercase tracking-widest border-t border-border/30"
      on:click={() => (showConnectModal = true)}
    >
      <span class="w-4 h-4 rounded bg-muted flex items-center justify-center group-hover:bg-primary/10 transition-colors">+</span>
      Add another server
    </button>
  {/if}
</div>

{#if showConnectModal}
  <ConnectToServerModal
    defaultUrl=""
    on:close={() => (showConnectModal = false)}
    on:connected={() => (showConnectModal = false)}
  />
{/if}
