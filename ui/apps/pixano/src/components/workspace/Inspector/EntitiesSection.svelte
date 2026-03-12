<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { Snippet } from "svelte";

  import { Eye, EyeClosed, FunnelSimple, MagnifyingGlass, Question, X } from "phosphor-svelte";
  import { Popover } from "bits-ui";

  import { IconButton, type Entity } from "$lib/ui";

  import { toggleAnnotationDisplayControl } from "$lib/utils/displayControl";
  import { GROUND_TRUTH, OTHER } from "$lib/constants/workspaceConstants";
  import { annotations } from "$lib/stores/workspaceStores.svelte";
  import OptionsAndFilters from "./OptionsAndFilters.svelte";

  interface Props {
    sourceLabel?: { name: string; kind: string };
    countText: string;
    searchQuery?: string;
    activeFilters?: string[];
    onSearchQueryChange?: (query: string) => void;
    onClearSearch?: () => void;
    onFilter?: (entities: Entity[]) => void;
    onConfidenceThresholdChange?: () => void;
    children?: Snippet;
    modelSelection?: Snippet;
  }

  let {
    sourceLabel = undefined,
    countText,
    searchQuery = "",
    activeFilters = [],
    onSearchQueryChange,
    onClearSearch,
    onFilter,
    onConfidenceThresholdChange,
    children,
    modelSelection,
  }: Props = $props();

  const modelName = $derived(sourceLabel?.name ?? OTHER);
  const sectionTitle = $derived.by(() => {
    if (!sourceLabel) return "Entity Explorer";
    if (sourceLabel.kind.toLowerCase() === "global") return "Entity Explorer";
    return sourceLabel.kind === "ground_truth"
      ? GROUND_TRUTH
      : `${sourceLabel.kind} - ${sourceLabel.name}`;
  });

  let showFilters = $state(false);

  const visibilityStatus = $derived(
    annotations.value.length > 0 && annotations.value.every((ann) => ann.ui.displayControl.hidden)
      ? "hidden"
      : "shown",
  );

  const tooltipContent = $derived(
    visibilityStatus === "hidden" ? `Show ${modelName} objects` : `Hide ${modelName} objects`,
  );

  const hasActiveFilters = $derived(activeFilters.length > 0);

  const handleVisibilityIconClick = () => {
    const isHidden = visibilityStatus === "hidden";
    annotations.update((anns) =>
      anns.map((ann) => {
        //return isAnnFromSource(ann) ? toggleAnnotationDisplayControl(ann, "hidden", !isHidden) : ann;
        //TMP(?) now that there is only a global source group, we change vis for all
        return toggleAnnotationDisplayControl(ann, "hidden", !isHidden);
      }),
    );
  };

  const handleSearchInput = (event: Event) => {
    onSearchQueryChange?.((event.currentTarget as HTMLInputElement).value);
  };

  const clearSearch = () => {
    if (onClearSearch) {
      onClearSearch();
      return;
    }
    onSearchQueryChange?.("");
  };
</script>

<section class="h-full min-h-0 flex flex-col overflow-hidden rounded-xl border border-border/50 bg-card/60">
  <div class="relative z-20 shrink-0 px-2.5 py-2.5 space-y-2.5 border-b border-border/40 bg-card/95 backdrop-blur">
    <div class="flex items-center gap-2 text-foreground">
      <IconButton {tooltipContent} onclick={handleVisibilityIconClick} class="h-8 w-8 rounded-lg">
        {#if visibilityStatus === "hidden"}
          <EyeClosed weight="regular" class="h-4 w-4" />
        {:else}
          <Eye class="h-4 w-4" />
        {/if}
      </IconButton>

      <h3 class="text-xs font-semibold uppercase tracking-wider text-muted-foreground grow truncate">
        {sectionTitle}
      </h3>

      {@render modelSelection?.()}

      <span
        class="text-xs text-muted-foreground tabular-nums bg-muted rounded-full px-2 py-0.5"
        title="object count - (filtered / total) if some objects are filtered out"
      >
        {countText}
      </span>
    </div>

    <div class="flex items-center gap-2">
      <div class="relative flex-1">
        <MagnifyingGlass class="h-3.5 w-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground/70 pointer-events-none" />
        <input
          type="text"
          placeholder="Quick search across all attributes"
          value={searchQuery}
          oninput={handleSearchInput}
          class="h-9 w-full rounded-lg border border-border/60 bg-background/80 pl-8 pr-8 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/40"
        />
        {#if searchQuery.length > 0}
          <button
            type="button"
            onclick={clearSearch}
            class="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Clear search"
            title="Clear search"
          >
            <X class="h-3.5 w-3.5" />
          </button>
        {/if}
      </div>

      <Popover.Root>
        <Popover.Trigger
          type="button"
          class="h-8 w-8 shrink-0 inline-flex items-center justify-center rounded-lg border border-border/60 bg-background text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
          title="Search help"
          aria-label="Search help"
        >
          <Question class="h-4 w-4" />
        </Popover.Trigger>
        <Popover.Content class="z-[120] w-80 rounded-lg border border-border bg-card p-3 text-foreground shadow-2xl ring-1 ring-border/70 outline-none space-y-2.5">
          <div class="space-y-0.5">
            <p class="text-xs font-semibold tracking-wide text-foreground">Search help</p>
            <p class="text-[11px] leading-relaxed text-muted-foreground">
              Default behavior is global search across indexed entity attributes.
            </p>
          </div>

          <div class="space-y-1.5 text-[11px]">
            <div class="flex items-center justify-between gap-2">
              <span class="text-muted-foreground">Free text</span>
              <code class="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px]">car blue</code>
            </div>
            <div class="flex items-center justify-between gap-2">
              <span class="text-muted-foreground">Field filter</span>
              <code class="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px]">color:blue</code>
            </div>
            <div class="flex items-center justify-between gap-2">
              <span class="text-muted-foreground">Numeric compare</span>
              <code class="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px]">score&gt;=0.80</code>
            </div>
            <div class="flex items-center justify-between gap-2">
              <span class="text-muted-foreground">Exclude term</span>
              <code class="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px]">-occluded</code>
            </div>
          </div>
        </Popover.Content>
      </Popover.Root>

      <button
        type="button"
        onclick={() => (showFilters = !showFilters)}
        class={`h-8 shrink-0 inline-flex items-center gap-1.5 rounded-lg border px-2 transition-colors ${
          showFilters
            ? "border-primary/40 bg-primary/10 text-primary"
            : "border-border/60 bg-background text-muted-foreground hover:text-foreground hover:bg-accent"
        }`}
        title={showFilters ? "Hide advanced rule builder" : "Show advanced rule builder"}
        aria-label={showFilters ? "Hide advanced rule builder" : "Show advanced rule builder"}
      >
        <FunnelSimple class="h-4 w-4" />
        <span class="text-[11px] font-semibold tracking-wide">Rules</span>
      </button>
    </div>

    {#if showFilters}
      <div class="rounded-md border border-border/40 bg-muted/25 px-2 py-1.5 text-[10px] text-muted-foreground">
        Rule builder creates exact typed constraints and is combined with search.
      </div>
    {/if}

    {#if hasActiveFilters}
      <div class="flex flex-wrap gap-1">
        {#each activeFilters as activeFilter}
          <span
            class="max-w-full truncate rounded-full bg-primary/10 text-primary text-[10px] px-2 py-0.5 font-medium"
            title={activeFilter}
          >
            {activeFilter}
          </span>
        {/each}
      </div>
    {/if}

    {#if showFilters}
      <OptionsAndFilters
        onFilter={onFilter}
        onConfidenceThresholdChange={onConfidenceThresholdChange}
      />
    {/if}
  </div>

  <div class="relative z-0 flex-1 min-h-0 overflow-y-auto custom-scrollbar px-1.5 py-2">
    <div class="flex flex-col gap-1.5 px-0.5">
      {@render children?.()}
    </div>
  </div>
</section>

<style>
  .custom-scrollbar::-webkit-scrollbar {
    width: 4px;
  }
  .custom-scrollbar::-webkit-scrollbar-track {
    background: transparent;
  }
  .custom-scrollbar::-webkit-scrollbar-thumb {
    background: hsl(var(--border));
    border-radius: 10px;
  }
  .custom-scrollbar::-webkit-scrollbar-thumb:hover {
    background: hsl(var(--muted-foreground) / 0.3);
  }
</style>
