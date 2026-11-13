<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { ArrowsClockwise, ChartBarHorizontal, Warning } from "phosphor-svelte";

  import OverviewCard from "./OverviewCard.svelte";
  import type { OverviewCard as Card, DatasetOverview } from "$lib/api/overviewApi";
  import { groupedCards, overviewTitle, statisticNames } from "$lib/utils/overview";

  type Props = {
    /** The overview of the records the filters keep; none when it could not be read. */
    overview: DatasetOverview | null;
    /** Why it could not be read. */
    error?: string;
    /** Per card, per bar, whether the explorer's filters keep its records alone. */
    kept: Record<string, boolean[]>;
    /** Whether the cards compare the splits. */
    bySplit: boolean;
    /** The overview of other filters is being read: the one shown is about to go. */
    loading?: boolean;
    /** A semantic search is under way: the overview shows the records the filters keep, unranked. */
    semanticActive?: boolean;
    /** What the overview says of a filter it could not add. */
    notice?: string;
    /**
     * Whether the statistics job can run here — a job queue on which a worker declared the job, even
     * if it is stopped now —; null until the server has said.
     */
    statisticsJobRuns: boolean | null;
    /** The overview is being read again, as a person asked. */
    readingAgain?: boolean;
    onToggleSplit: () => void;
    /** A card's bar was clicked, or chosen in its table of values. */
    onBarClick: (card: Card, index: number) => void;
    /** A card's filter is to go. */
    onClear: (card: Card) => void;
    /** Read the overview again: after it failed, or once the statistics it waits for are computed. */
    onReadAgain: () => void;
  };
  let {
    overview,
    error = "",
    kept,
    bySplit,
    loading = false,
    semanticActive = false,
    notice = "",
    statisticsJobRuns,
    readingAgain = false,
    onToggleSplit,
    onBarClick,
    onClear,
    onReadAgain,
  }: Props = $props();

  const parts = $derived(overview ? groupedCards(overview.cards) : []);
  const comparable = $derived(overview !== null && overview.splits.length > 1);
  const toCompute = $derived(overview?.statistics_to_compute ?? []);
  // Reading again over a reading under way would take its place: the buttons wait for it.
  const busy = $derived(loading || readingAgain);
  const actionClass =
    "inline-flex h-7 items-center gap-1 rounded-lg border border-border bg-background px-2.5 text-[11px] font-bold uppercase tracking-wider text-muted-foreground hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60";
</script>

<div class="flex-1 min-h-0 overflow-y-auto p-4">
  {#if overview === null}
    <div class="flex flex-wrap items-center gap-3" role="alert">
      <p class="flex items-center gap-2 text-sm text-destructive">
        <Warning size={16} />
        {error || "The overview could not be read."}
      </p>
      <button type="button" onclick={onReadAgain} disabled={busy} class={actionClass}>
        <ArrowsClockwise size={12} />
        {readingAgain ? "Reading…" : "Try again"}
      </button>
    </div>
  {:else}
    <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
      <p class="flex items-center gap-2 text-sm text-muted-foreground tabular-nums">
        <ChartBarHorizontal size={16} class="text-primary" />
        {overviewTitle(overview.records, overview.total_records)}
      </p>
      {#if comparable}
        <label
          class="inline-flex cursor-pointer items-center gap-2 text-xs font-medium text-foreground"
        >
          <input
            type="checkbox"
            checked={bySplit}
            onchange={onToggleSplit}
            disabled={loading}
            class="accent-primary"
          />
          Compare splits
        </label>
      {/if}
    </div>

    {#if semanticActive}
      <p class="mb-3 text-xs text-muted-foreground">
        A semantic search ranks records: the overview counts every record the filters keep,
        unranked.
      </p>
    {/if}

    {#if notice}
      <p class="mb-3 text-xs text-warning" role="status">{notice}</p>
    {/if}

    {#if toCompute.length > 0}
      <div
        class="mb-4 flex flex-wrap items-center gap-3 rounded-xl border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-foreground"
      >
        <span class="flex-1">
          Not computed yet: {statisticNames(toCompute)}.
          {#if statisticsJobRuns}
            The statistics job an import queues computes them: read the overview again once it is
            done. If this dataset was imported without them, they stay uncomputed: this interface
            cannot start that job yet.
          {:else if statisticsJobRuns === false}
            The statistics job computes them, where pixano-worker runs it.
          {/if}
        </span>
        {#if statisticsJobRuns}
          <button type="button" onclick={onReadAgain} disabled={busy} class={actionClass}>
            <ArrowsClockwise size={12} />
            {readingAgain ? "Reading…" : "Read again"}
          </button>
        {/if}
      </div>
    {/if}

    <div
      class="transition-opacity {loading ? 'pointer-events-none opacity-60' : ''}"
      aria-busy={loading}
    >
      {#each parts as part (part.group)}
        <section class="mb-6">
          <h2 class="mb-2 text-label">{part.title}</h2>
          <div class="grid grid-cols-1 items-start gap-3 md:grid-cols-2 xl:grid-cols-3">
            {#each part.cards as card (card.id)}
              <OverviewCard
                {card}
                splits={bySplit ? overview.splits : []}
                kept={kept[card.id] ?? []}
                onBarClick={(index) => onBarClick(card, index)}
                onClear={() => onClear(card)}
              />
            {/each}
          </div>
        </section>
      {/each}
    </div>
  {/if}
</div>
