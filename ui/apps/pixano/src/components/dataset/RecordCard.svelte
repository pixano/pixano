<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { ArrowRight, FilmStrip, Sparkle } from "phosphor-svelte";

  import type { RecordCard } from "$lib/types/dataset";
  import { cardLayout } from "$lib/utils/cardLayout";

  interface Props {
    record: RecordCard;
    /** 1-based rank in ranked (semantic / find-similar) mode. */
    rank?: number;
    onOpen: (id: string) => void;
    onFindSimilar?: (id: string) => void;
  }

  let { record, rank, onOpen, onFindSimilar }: Props = $props();

  const layout = $derived(cardLayout(record.previews));
  const primaryIsVideo = $derived(layout.media[0]?.resource === "sframes");

  const statusToneClass = (status: string): string => {
    switch (status) {
      case "validated":
      case "done":
        return "bg-success/10 text-success";
      case "in_progress":
      case "reviewed":
        return "bg-warning/10 text-warning";
      default:
        return "bg-muted text-muted-foreground";
    }
  };

  const overlayButtonClass =
    "flex h-10 w-10 items-center justify-center rounded-full bg-background/90 text-foreground shadow-sm transition-colors hover:bg-background hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
</script>

<div
  role="button"
  tabindex="0"
  aria-label="Open record {record.id}"
  onclick={() => onOpen(record.id)}
  onkeydown={(event: KeyboardEvent) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onOpen(record.id);
    }
  }}
  class="group/card relative flex flex-col overflow-hidden bg-card rounded-2xl border border-border shadow-sm hover:shadow-2xl hover:border-primary/30 hover:-translate-y-1.5 transition-all duration-500 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
>
  <!-- Media area -->
  <div class="relative aspect-square w-full overflow-hidden bg-muted">
    {#if layout.kind === "single" || layout.kind === "many"}
      <img
        src={layout.media[0].url}
        alt="record preview"
        loading="lazy"
        class="w-full h-full object-cover transition-transform duration-700 group-hover/card:scale-105"
      />
    {:else if layout.kind === "duo"}
      <div class="grid grid-cols-2 gap-px bg-border w-full h-full">
        {#each layout.media as preview (preview.name)}
          <img
            src={preview.url}
            alt="record preview — {preview.name}"
            loading="lazy"
            class="w-full h-full object-cover transition-transform duration-700 group-hover/card:scale-105"
          />
        {/each}
      </div>
    {:else if layout.kind === "imageText"}
      <div class="flex flex-col w-full h-full">
        <div class="relative flex-[3] min-h-0 overflow-hidden">
          <img
            src={layout.media[0].url}
            alt="record preview"
            loading="lazy"
            class="w-full h-full object-cover transition-transform duration-700 group-hover/card:scale-105"
          />
        </div>
        <div
          class="flex-[2] min-h-0 p-3 text-xs text-muted-foreground font-mono leading-relaxed border-t border-border/40 bg-surface-2 overflow-hidden"
        >
          <p class="line-clamp-4">{layout.text?.excerpt}</p>
        </div>
      </div>
    {:else if layout.kind === "textOnly"}
      <div class="w-full h-full p-4 bg-surface-2 overflow-hidden">
        <p class="text-xs text-muted-foreground font-mono leading-relaxed line-clamp-[10]">
          {layout.text?.excerpt}
        </p>
      </div>
    {:else}
      <!-- No previews at all: typographic placeholder -->
      <div class="w-full h-full flex items-center justify-center bg-primary/5">
        <span class="text-4xl font-black text-primary/30 select-none uppercase">
          {record.id.slice(0, 1) || "?"}
        </span>
      </div>
    {/if}

    <!-- Badges -->
    {#if primaryIsVideo}
      <span
        class="absolute top-2 left-2 inline-flex items-center gap-1 px-2 py-1 rounded-full bg-background/80 backdrop-blur-md text-[10px] font-black uppercase tracking-widest text-foreground"
      >
        <FilmStrip size={12} />
        Video
      </span>
    {/if}
    {#if layout.extraCount > 0}
      <span
        class="absolute bottom-2 right-2 px-2 py-0.5 rounded-full bg-background/80 backdrop-blur-md text-[10px] font-black uppercase tracking-widest text-foreground"
      >
        +{layout.extraCount}
        {layout.extraCount === 1 ? "view" : "views"}
      </span>
    {/if}
    {#if rank !== undefined}
      <span
        class="absolute top-2 right-2 inline-flex items-center gap-1.5 text-[10px] font-black tabular-nums"
      >
        <span class="px-2 py-0.5 rounded-full bg-primary text-primary-foreground">#{rank}</span>
        {#if record.distance !== undefined}
          <span
            class="px-2 py-0.5 rounded-full bg-background/80 backdrop-blur-md font-mono text-foreground"
          >
            {record.distance.toFixed(3)}
          </span>
        {/if}
      </span>
    {/if}

    <!-- Hover overlay actions -->
    <div
      class="absolute inset-0 bg-black/40 backdrop-blur-[2px] opacity-0 group-hover/card:opacity-100 transition-all duration-300 flex items-center justify-center gap-3"
    >
      <button
        type="button"
        title="Open record"
        aria-label="Open record"
        class="{overlayButtonClass} translate-y-4 group-hover/card:translate-y-0 transition-transform duration-300"
        onclick={(event: MouseEvent) => {
          event.stopPropagation();
          onOpen(record.id);
        }}
      >
        <ArrowRight size={17} />
      </button>
      {#if onFindSimilar}
        <button
          type="button"
          title="Find similar records"
          aria-label="Find similar records"
          class="{overlayButtonClass} translate-y-4 group-hover/card:translate-y-0 transition-transform duration-300 delay-75"
          onclick={(event: MouseEvent) => {
            event.stopPropagation();
            onFindSimilar(record.id);
          }}
        >
          <Sparkle size={17} />
        </button>
      {/if}
    </div>
  </div>

  <!-- Meta strip -->
  <div class="px-3 py-2 flex items-center gap-2 border-t border-border/40 min-h-[38px]">
    <span class="font-mono text-[11px] text-muted-foreground truncate flex-1" title={record.id}>
      {record.id}
    </span>
    {#if record.split}
      <span
        class="px-1.5 py-0.5 rounded-full bg-info/10 text-info text-[10px] font-bold uppercase tracking-wide shrink-0"
      >
        {record.split}
      </span>
    {/if}
    {#if record.status}
      <span
        class="px-1.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide shrink-0 {statusToneClass(
          record.status,
        )}"
      >
        {record.status}
      </span>
    {/if}
  </div>
</div>
