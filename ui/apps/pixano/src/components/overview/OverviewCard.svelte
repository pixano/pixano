<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Warning, X } from "phosphor-svelte";

  import OverviewChart from "./OverviewChart.svelte";
  import type { OverviewCard } from "$lib/api/overviewApi";
  import {
    allDistinct,
    cardChart,
    cardSummary,
    computedLabel,
    counted,
    formatShare,
    notableExplanation,
    SUBJECT_WORDS,
    unfilteredReason,
  } from "$lib/utils/overview";

  type Props = {
    card: OverviewCard;
    /** The overview's splits when it compares them; none otherwise. */
    splits: string[];
    /** Per bar, whether the explorer's filters keep its records alone: clicking it again keeps all. */
    kept: boolean[];
    /** A bar was clicked, or chosen in the table of values: its index. None where nothing filters. */
    onBarClick?: (index: number) => void;
    /** The filter of the card's column is to go. */
    onClear?: () => void;
  };
  let { card, splits, kept, onBarClick, onClear }: Props = $props();

  const chart = $derived(cardChart(card, splits));
  const summary = $derived(cardSummary(card));
  const differs = $derived(chart.notable.some((pointed) => pointed));
  const held = $derived(card.population - card.missing);
  const canFilter = $derived(card.filter_column !== null && onBarClick !== undefined);
  const subject = $derived(SUBJECT_WORDS[card.subject]);
  const computed = $derived(computedLabel(card));
  const everyValueDiffers = $derived(allDistinct(card));
</script>

<article
  class="flex min-w-0 flex-col gap-2 rounded-xl border border-border/60 bg-background p-3 shadow-sm"
>
  <header class="flex items-start justify-between gap-2">
    <h3 class="min-w-0 truncate text-sm font-semibold text-foreground" title={card.label}>
      {card.label}{#if card.unit}<span class="ml-1 text-xs font-normal text-muted-foreground">
          ({card.unit})
        </span>{/if}
    </h3>
    <div class="flex shrink-0 items-center gap-1.5">
      {#if differs}
        <span
          class="inline-flex items-center gap-1 rounded-full bg-destructive/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-destructive"
          title={notableExplanation()}
        >
          <Warning size={11} />
          Splits differ
        </span>
      {/if}
      {#if card.filtered && onClear}
        <button
          type="button"
          onclick={onClear}
          class="inline-flex h-6 items-center gap-1 rounded-md border border-border bg-background px-2 text-[10px] font-bold uppercase tracking-wider text-muted-foreground hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          aria-label={`Clear the filter on ${card.label}`}
        >
          <X size={11} />
          Clear
        </button>
      {/if}
    </div>
  </header>
  <p class="text-xs text-muted-foreground tabular-nums">{summary.join(" · ")}</p>

  {#if held === 0}
    <p class="py-6 text-center text-xs text-muted-foreground">
      No value among these {subject.many}.
    </p>
  {:else if everyValueDiffers}
    <p class="py-6 text-center text-xs text-muted-foreground">
      Every value differs: {counted(card.distinct, { one: "value", many: "values" })} for
      {counted(held, subject)}.
    </p>
  {:else}
    <OverviewChart
      labels={chart.labels}
      series={chart.series}
      shares={chart.shares}
      notable={chart.notable}
      clickable={chart.clickable}
      selected={chart.selected}
      filtered={card.filtered === true}
      horizontal={card.kind === "values"}
      description={`${card.label}: ${summary.join(", ")}`}
      onBarClick={canFilter ? onBarClick : undefined}
    />
  {/if}

  {#if held > 0}
    <div class="flex flex-col gap-0.5 text-[11px] text-muted-foreground">
      {#if card.filtered}
        <p>Counted without its own filter: the bars it keeps stand out.</p>
      {:else if canFilter}
        <p>Click a bar to keep the records it counts; click it again to keep them all.</p>
      {:else}
        <p>{unfilteredReason(card)}</p>
      {/if}
      {#if computed}
        <p>{computed}</p>
      {/if}
    </div>
    <details class="text-xs">
      <summary
        class="cursor-pointer select-none text-[11px] font-medium text-muted-foreground hover:text-foreground"
      >
        Values
      </summary>
      <table class="mt-1 w-full table-fixed text-left tabular-nums">
        <thead class="text-[10px] uppercase tracking-wider text-muted-foreground">
          <tr>
            <th class="w-2/5 py-1 font-semibold">Value</th>
            <th class="py-1 font-semibold">{subject.many}</th>
            {#if chart.shares}
              {#each chart.series as one (one.colorIndex)}
                <th class="py-1 font-semibold">{one.label}</th>
              {/each}
              <th class="py-1"><span class="sr-only">Splits</span></th>
            {/if}
            {#if canFilter}
              <th class="py-1"><span class="sr-only">Filter</span></th>
            {/if}
          </tr>
        </thead>
        <tbody>
          {#each chart.labels as label, index (index)}
            <tr class="border-t border-border/40 {chart.selected[index] ? 'font-semibold' : ''}">
              <td class="truncate py-1 pr-2" title={label}>{label}</td>
              <td class="py-1">{chart.counts[index].toLocaleString()}</td>
              {#if chart.shares}
                {#each chart.series as one (one.colorIndex)}
                  <td class="py-1">{formatShare(one.values[index])}</td>
                {/each}
                <td class="py-1 text-[10px] font-bold uppercase text-destructive">
                  {chart.notable[index] ? "Differ" : ""}
                </td>
              {/if}
              {#if canFilter}
                <td class="py-1 text-right">
                  {#if chart.clickable[index]}
                    <button
                      type="button"
                      onclick={() => onBarClick?.(index)}
                      aria-pressed={kept[index] ?? false}
                      aria-label={`Keep only ${label}, ${card.label}`}
                      class="rounded px-1.5 py-0.5 text-[10px] font-semibold text-primary hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring aria-pressed:bg-primary/15"
                    >
                      Keep only
                    </button>
                  {/if}
                </td>
              {/if}
            </tr>
          {/each}
        </tbody>
      </table>
    </details>
  {/if}
</article>
