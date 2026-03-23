<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { X } from "phosphor-svelte";

  import type { VlmPromptDebugEntry } from "$lib/stores/vqaStores.svelte";

  interface Props {
    entry: VlmPromptDebugEntry;
    onClose?: () => void;
  }

  let { entry, onClose }: Props = $props();

  let formattedPrompt = $derived(
    typeof entry.prompt === "string" ? entry.prompt : JSON.stringify(entry.prompt, null, 2),
  );

  let formattedTime = $derived(new Date(entry.timestamp).toLocaleTimeString());

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === "Escape") onClose?.();
  }
</script>

<svelte:window onkeydown={handleKeyDown} />

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
  onclick={onClose}
>
  <div
    onclick={(e) => e.stopPropagation()}
    class="w-[36rem] h-[34rem] flex flex-col rounded-2xl bg-card border border-border/50 shadow-2xl"
  >
    <!-- Header -->
    <div class="flex items-center justify-between px-6 pt-6 pb-4 shrink-0">
      <h2 class="text-base font-semibold text-foreground">Last VLM Prompt</h2>
      <button
        type="button"
        onclick={onClose}
        class="h-7 w-7 flex items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
      >
        <X weight="regular" size={16} />
      </button>
    </div>

    <!-- Metadata -->
    <div class="px-6 pb-3 shrink-0 flex flex-wrap gap-3 text-[12px]">
      <div class="flex items-center gap-1.5 px-2 py-1 rounded-md bg-muted text-muted-foreground">
        <span class="font-medium">Model</span>
        <span class="text-foreground">{entry.model}</span>
      </div>
      <div class="flex items-center gap-1.5 px-2 py-1 rounded-md bg-muted text-muted-foreground">
        <span class="font-medium">Provider</span>
        <span class="text-foreground">{entry.provider || "—"}</span>
      </div>
      <div class="flex items-center gap-1.5 px-2 py-1 rounded-md bg-muted text-muted-foreground">
        <span class="font-medium">Temp</span>
        <span class="text-foreground font-mono">{entry.temperature.toFixed(1)}</span>
      </div>
      <div class="flex items-center gap-1.5 px-2 py-1 rounded-md bg-muted text-muted-foreground">
        <span class="font-medium">Images</span>
        <span class="text-foreground">{entry.imageCount}</span>
      </div>
      <div class="flex items-center gap-1.5 px-2 py-1 rounded-md bg-muted text-muted-foreground">
        <span class="font-medium">Time</span>
        <span class="text-foreground">{formattedTime}</span>
      </div>
    </div>

    <!-- Prompt content -->
    <div class="flex-1 min-h-0 px-6 pb-6">
      <pre
        class="w-full h-full overflow-auto rounded-xl border border-border bg-muted/30 p-4 text-[12px] leading-relaxed font-mono text-foreground whitespace-pre-wrap break-words">{formattedPrompt}</pre>
    </div>
  </div>
</div>
