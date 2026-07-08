<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { ArrowUp, CircleNotch, Folder } from "phosphor-svelte";

  import { browseServerFolders } from "$lib/api/ioApi";
  import type { FolderBrowseResponse } from "$lib/api/restTypes";

  interface Props {
    initialPath: string;
    onSelect: (path: string) => void;
    onClose: () => void;
  }

  let { initialPath, onSelect, onClose }: Props = $props();

  let listing = $state<FolderBrowseResponse | null>(null);
  let loading = $state(true);
  let error = $state("");
  let browseToken = 0;

  async function navigate(path: string) {
    loading = true;
    error = "";
    const token = ++browseToken;
    try {
      const result = await browseServerFolders(path);
      if (token !== browseToken) return;
      listing = result;
    } catch (err: unknown) {
      if (token !== browseToken) return;
      error = err instanceof Error ? err.message : "Could not list the folder.";
    } finally {
      if (token === browseToken) loading = false;
    }
  }

  $effect(() => {
    // Start where the user already typed a path (falls back to home on error).
    void navigate(initialPath.trim().startsWith("/") ? initialPath.trim() : "");
  });

  function retryHome() {
    void navigate("");
  }

  const HINT_LABELS: Record<string, string> = { pixano: "pixano dataset", lerobot: "lerobot" };
</script>

<div class="space-y-2 rounded-xl border border-border bg-card/60 p-3">
  <div class="flex items-center gap-2">
    {#if listing?.parent}
      <button
        type="button"
        class="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs text-muted-foreground hover:text-foreground"
        onclick={() => listing && listing.parent && void navigate(listing.parent)}
      >
        <ArrowUp weight="bold" class="h-3 w-3" />
        Up
      </button>
    {/if}
    <p
      class="min-w-0 flex-1 truncate font-mono text-[11px] text-muted-foreground"
      title={listing?.path}
    >
      {listing?.path ?? ""}
    </p>
  </div>

  {#if loading}
    <div class="flex items-center gap-2 py-4 text-xs text-muted-foreground">
      <CircleNotch weight="regular" class="h-4 w-4 animate-spin" />
      Listing folders…
    </div>
  {:else if error}
    <div class="space-y-1 py-2">
      <p class="text-xs text-destructive">{error}</p>
      <button type="button" class="text-xs text-primary hover:underline" onclick={retryHome}>
        Back to the home folder
      </button>
    </div>
  {:else if listing}
    <div class="max-h-52 space-y-0.5 overflow-y-auto">
      {#each listing.entries as entry (entry.path)}
        <button
          type="button"
          class="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs text-foreground hover:bg-primary/5"
          ondblclick={() => onSelect(entry.path)}
          onclick={() => void navigate(entry.path)}
          title="Click to open, double-click to select"
        >
          <Folder weight="regular" class="h-4 w-4 shrink-0 text-primary/70" />
          <span class="min-w-0 flex-1 truncate">{entry.name}</span>
          {#if HINT_LABELS[entry.hint]}
            <span
              class="rounded-full border border-primary/30 px-1.5 py-0.5 text-[9px] text-primary"
            >
              {HINT_LABELS[entry.hint]}
            </span>
          {/if}
        </button>
      {:else}
        <p class="px-2 py-3 text-xs text-muted-foreground">No subfolders here.</p>
      {/each}
    </div>
  {/if}

  <div class="flex items-center justify-end gap-2 border-t border-border pt-2">
    <button
      type="button"
      class="text-xs text-muted-foreground hover:text-foreground"
      onclick={onClose}
    >
      Cancel
    </button>
    <button
      type="button"
      class="rounded-md border border-primary/60 px-2.5 py-1 text-xs font-medium text-primary hover:bg-primary/5 disabled:opacity-50"
      disabled={!listing}
      onclick={() => listing && onSelect(listing.path)}
    >
      Use this folder
    </button>
  </div>
</div>
