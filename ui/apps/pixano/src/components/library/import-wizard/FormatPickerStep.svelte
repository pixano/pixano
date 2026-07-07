<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { CircleNotch, MagicWand } from "phosphor-svelte";

  import type { IoFormatResponse } from "$lib/api/restTypes";

  interface Props {
    formats: IoFormatResponse[] | null;
    selected: string;
    onSelect: (format: string) => void;
  }

  let { formats, selected, onSelect }: Props = $props();

  const cardClass = (active: boolean) =>
    `w-full rounded-xl border p-4 text-left transition-colors ${
      active ? "border-primary bg-primary/5" : "border-border bg-card hover:border-primary/40"
    }`;
</script>

<div class="px-6 sm:px-7 pb-2 space-y-3">
  <p class="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Format</p>

  {#if formats === null}
    <div class="flex items-center gap-2 py-6 text-sm text-muted-foreground">
      <CircleNotch weight="regular" class="h-4 w-4 animate-spin" />
      Loading formats…
    </div>
  {:else}
    <div class="space-y-2">
      <button type="button" class={cardClass(selected === "")} onclick={() => onSelect("")}>
        <span class="flex items-center gap-2 text-sm font-medium text-foreground">
          <MagicWand weight="regular" class="h-4 w-4 text-primary" />
          Auto-detect
        </span>
        <span class="mt-1 block text-xs text-muted-foreground">
          Probe the source and pick the best matching format (a dataset.yaml at the source root is
          applied automatically).
        </span>
      </button>

      {#each formats.filter((format) => format.can_import) as format (format.name)}
        <button
          type="button"
          class={cardClass(selected === format.name)}
          onclick={() => onSelect(format.name)}
        >
          <span class="flex items-center justify-between text-sm font-medium text-foreground">
            {format.title || format.name}
            <span class="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              {format.name}
            </span>
          </span>
          <span class="mt-1 flex flex-wrap gap-1.5">
            {#each format.capabilities?.media_kinds ?? [] as kind (kind)}
              <span
                class="rounded-full border border-border px-2 py-0.5 text-[10px] text-muted-foreground"
              >
                {kind}
              </span>
            {/each}
            {#if format.capabilities?.supports_resume}
              <span
                class="rounded-full border border-primary/30 px-2 py-0.5 text-[10px] text-primary"
              >
                resumable
              </span>
            {/if}
          </span>
        </button>
      {/each}
    </div>
  {/if}
</div>
