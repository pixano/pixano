<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { ArrowCounterClockwise, Info } from "phosphor-svelte";

  import { colorByOptionLabel } from "./colorByLabels";
  import ColorSwatchPicker from "./ColorSwatchPicker.svelte";
  import {
    DEFAULT_RAMP,
    formatAttributeNumber,
    NO_VALUE_COLOR,
  } from "$lib/coloring/colorByPalette";
  import type { ColorLegend, LegendEntry, LegendUnit } from "$lib/coloring/colorResolver";
  import {
    colorByLegendOpen,
    resetColorByColors,
    resetColorByRange,
    setColorByRampColor,
    setColorByValueColor,
  } from "$lib/stores/colorByStore.svelte";
  import { annotationColors } from "$lib/stores/workspaceStores.svelte";

  const legend: ColorLegend | null = $derived(annotationColors.value.legend);
  let showKnownValues = $state(false);
  const rampGradient = $derived(
    legend?.kind === "numeric" ? `linear-gradient(90deg, ${legend.stops.join(", ")})` : "",
  );

  const UNIT_NAMES: Record<LegendUnit, [string, string]> = {
    objects: ["object", "objects"],
    annotations: ["annotation", "annotations"],
    tracks: ["track", "tracks"],
  };

  const countOf = (count: number, [one, many]: [string, string]) =>
    `${count} ${count === 1 ? one : many}`;

  function footnoteOf(current: ColorLegend): string | null {
    if (current.attribute.scope === "entity") return null;
    if (current.unit === "tracks") return "Shapes take the value of their track.";
    return current.kind === "numeric"
      ? "Objects and tracks show the average value of their annotations."
      : "Objects and tracks show the most frequent value of their annotations.";
  }

  const resetButtonClass =
    "inline-flex shrink-0 items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] text-muted-foreground transition-colors hover:bg-muted/40 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
</script>

{#snippet valueRow(entry: LegendEntry, attributeId: string)}
  <li class="flex items-center gap-2 rounded-md px-1.5 py-1 hover:bg-muted/40">
    <ColorSwatchPicker
      color={entry.color}
      label={`Color of ${entry.key}`}
      custom={entry.custom}
      onPick={(color) => setColorByValueColor(attributeId, entry.key, color)}
    />
    <span class="min-w-0 flex-1 truncate text-xs" title={entry.key}>{entry.key}</span>
    <span class="shrink-0 tabular-nums text-[10px] text-muted-foreground">{entry.count}</span>
  </li>
{/snippet}

{#snippet noValueRow(count: number, otherCount: number)}
  <li
    class="flex items-center gap-2 px-1.5 py-1"
    title={otherCount > 0
      ? "Includes annotations of other types, which do not have this attribute"
      : undefined}
  >
    <span
      class="h-4 w-4 shrink-0 rounded-full ring-1 ring-foreground/50"
      style={`background-color: ${NO_VALUE_COLOR}`}
      aria-hidden="true"
    ></span>
    <span class="min-w-0 flex-1 truncate text-xs text-muted-foreground">No value</span>
    <span class="shrink-0 tabular-nums text-[10px] text-muted-foreground">{count}</span>
  </li>
{/snippet}

{#if legend && colorByLegendOpen.value}
  {@const attributeId = legend.attribute.id}
  {@const noValueCount = legend.noValueCount + legend.otherCount}
  {@const footnote = footnoteOf(legend)}
  <section
    id="color-by-legend"
    aria-label={`Colors by ${colorByOptionLabel(legend.attribute)}`}
    class="space-y-1.5 rounded-lg border border-border/40 bg-background/70 p-2"
  >
    {#if legend.kind === "categorical"}
      {@const valueCount = legend.entries.length + legend.moreCount}
      <div class="flex items-center gap-2">
        <p class="min-w-0 flex-1 truncate text-[11px] text-muted-foreground">
          {countOf(valueCount, ["value", "values"])} · {countOf(
            legend.itemCount,
            UNIT_NAMES[legend.unit],
          )}
        </p>
        {#if legend.customized}
          <button
            type="button"
            class={resetButtonClass}
            title="Restore the automatic colors"
            onclick={() => resetColorByColors(attributeId)}
          >
            <ArrowCounterClockwise class="h-3 w-3" />
            Reset colors
          </button>
        {/if}
      </div>

      {#if legend.sharedColorCount > 0}
        <p class="flex items-start gap-1 text-[10px] leading-snug text-muted-foreground">
          <Info class="mt-px h-3 w-3 shrink-0" />
          {legend.sharedColorCount} values share a color: click a swatch to tell them apart.
        </p>
      {/if}

      {#if valueCount === 0 && noValueCount === 0}
        <p class="px-1.5 text-xs text-muted-foreground">No value in this record.</p>
      {/if}

      <ul class="flex flex-col gap-0.5">
        {#each legend.entries as entry (entry.key)}
          {@render valueRow(entry, attributeId)}
        {/each}
        {#if legend.moreCount > 0}
          <li class="px-1.5 text-[10px] text-muted-foreground">
            {countOf(legend.moreCount, ["more value", "more values"])}
          </li>
        {/if}
        {#if noValueCount > 0}
          {@render noValueRow(noValueCount, legend.otherCount)}
        {/if}
      </ul>

      {#if legend.knownEntries.length > 0}
        <button
          type="button"
          aria-expanded={showKnownValues}
          class="px-1.5 text-[11px] text-muted-foreground underline-offset-2 transition-colors hover:text-foreground hover:underline"
          onclick={() => (showKnownValues = !showKnownValues)}
        >
          {showKnownValues ? "Hide" : "Show"}
          {countOf(legend.knownEntries.length, ["value", "values"])} from other records
        </button>
        {#if showKnownValues}
          <ul class="flex flex-col gap-0.5">
            {#each legend.knownEntries as entry (entry.key)}
              {@render valueRow(entry, attributeId)}
            {/each}
          </ul>
        {/if}
      {/if}
    {:else}
      <div class="flex items-center gap-2">
        <p class="min-w-0 flex-1 truncate text-[11px] text-muted-foreground">
          {countOf(legend.itemCount, UNIT_NAMES[legend.unit])}
        </p>
        {#if legend.domain?.source === "seen"}
          <button
            type="button"
            class={resetButtonClass}
            title="Learn the range again from the next values"
            onclick={() => resetColorByRange(attributeId)}
          >
            <ArrowCounterClockwise class="h-3 w-3" />
            Reset range
          </button>
        {/if}
        {#if legend.customized}
          <button
            type="button"
            class={resetButtonClass}
            title="Restore the automatic colors"
            onclick={() => resetColorByColors(attributeId)}
          >
            <ArrowCounterClockwise class="h-3 w-3" />
            Reset colors
          </button>
        {/if}
      </div>

      <div class="flex items-center gap-2 px-1.5">
        <ColorSwatchPicker
          color={legend.low}
          label="Color of the lowest values"
          custom={legend.low !== DEFAULT_RAMP.low}
          onPick={(color) => setColorByRampColor(attributeId, "low", color)}
        />
        <div
          class="h-2.5 flex-1 rounded-full ring-1 ring-foreground/50"
          style={`background: ${rampGradient}`}
          role="img"
          aria-label={legend.domain
            ? `Colors from ${formatAttributeNumber(legend.domain.min)} to ${formatAttributeNumber(legend.domain.max)}`
            : "Color ramp"}
        ></div>
        <ColorSwatchPicker
          color={legend.high}
          label="Color of the highest values"
          custom={legend.high !== DEFAULT_RAMP.high}
          onPick={(color) => setColorByRampColor(attributeId, "high", color)}
        />
      </div>

      {#if legend.domain}
        <div
          class="flex items-center justify-between gap-2 px-1.5 text-[10px] tabular-nums text-muted-foreground"
        >
          <span>{formatAttributeNumber(legend.domain.min)}</span>
          <span class="truncate">
            {legend.domain.source === "fixed" ? "Fixed range" : "Range seen so far"}
          </span>
          <span>{formatAttributeNumber(legend.domain.max)}</span>
        </div>
      {:else}
        <p class="px-1.5 text-xs text-muted-foreground">No value in this record.</p>
      {/if}

      {#if noValueCount > 0}
        <ul class="flex flex-col gap-0.5">
          {@render noValueRow(noValueCount, legend.otherCount)}
        </ul>
      {/if}
    {/if}

    {#if footnote}
      <p class="px-1.5 text-[10px] leading-snug text-muted-foreground">{footnote}</p>
    {/if}
  </section>
{/if}
