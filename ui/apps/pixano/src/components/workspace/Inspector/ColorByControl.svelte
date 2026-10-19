<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Select, Tooltip } from "bits-ui";
  import { CaretDown, Check, Palette, Swatches } from "phosphor-svelte";

  import { colorByGroupHeading, colorByOptionLabel } from "./colorByLabels";
  import { ENTITY_COLOR_MODE, type ColorByAttribute } from "$lib/coloring/colorByCatalogue";
  import {
    colorByCatalogue,
    colorByLegendOpen,
    selectColorBy,
  } from "$lib/stores/colorByStore.svelte";
  import { annotationColors, itemMetas } from "$lib/stores/workspaceStores.svelte";
  import { WorkspaceType } from "$lib/types/dataset";
  import { TooltipContent } from "$lib/ui";
  import { handleMenuKeydown } from "$lib/utils/menuKeys";

  let open = $state(false);

  const attributes = $derived(colorByCatalogue.value.attributes);
  const mode = $derived(annotationColors.value.mode);
  const selectedAttribute = $derived(mode.kind === "attribute" ? mode.attribute : null);
  const selectedId = $derived(selectedAttribute?.id ?? ENTITY_COLOR_MODE);
  const triggerLabel = $derived(
    selectedAttribute ? colorByOptionLabel(selectedAttribute) : "Entity",
  );
  const isUnavailable = $derived(attributes.length === 0);
  const isHidden = $derived(itemMetas.value?.type === WorkspaceType.PCL_3D);

  // Options grouped under their heading, in catalogue order.
  const groups = $derived.by(() => {
    const byHeading = new Map<string, ColorByAttribute[]>();
    for (const attribute of attributes) {
      const heading = colorByGroupHeading(attribute);
      const group = byHeading.get(heading);
      if (group) group.push(attribute);
      else byHeading.set(heading, [attribute]);
    }
    return [...byHeading].map(([heading, groupAttributes]) => ({
      heading,
      attributes: groupAttributes,
    }));
  });

  const legendTooltip = $derived(colorByLegendOpen.value ? "Hide the legend" : "Show the legend");

  function onKeydown(event: KeyboardEvent) {
    handleMenuKeydown(event, open, () => (open = false));
  }

  const triggerClass =
    "inline-flex h-8 w-full items-center justify-between gap-1.5 rounded-lg border border-border/60 bg-background px-2 text-xs font-medium shadow-sm transition-colors hover:bg-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60";
  const contentClass =
    "z-[130] max-h-72 w-[var(--bits-select-anchor-width)] min-w-56 overflow-y-auto rounded-2xl border border-border/50 bg-popover/95 p-1.5 text-popover-foreground shadow-elevation-2 backdrop-blur-md";
  const itemClass =
    "flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-xs outline-none transition-colors data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground";
  const headingClass =
    "px-2 pt-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground";
</script>

{#if !isHidden}
  <div class="flex items-center gap-2">
    <Palette class="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
    <span
      class="shrink-0 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground"
      aria-hidden="true"
    >
      Color by
    </span>
    <div class="min-w-0 flex-1">
      <Select.Root
        type="single"
        bind:open
        value={selectedId}
        disabled={isUnavailable}
        onValueChange={(next: string) => {
          if (next) selectColorBy(next);
        }}
      >
        <Select.Trigger
          aria-label={`Color by: ${triggerLabel}`}
          title={isUnavailable ? "This dataset has no attribute to color by" : triggerLabel}
          onkeydown={onKeydown}
          class={triggerClass}
        >
          {#snippet children()}
            <span class="truncate">{triggerLabel}</span>
            <CaretDown size={11} class="shrink-0 text-muted-foreground" />
          {/snippet}
        </Select.Trigger>
        <Select.Portal>
          <Select.Content sideOffset={6} onkeydown={onKeydown} class={contentClass}>
            <Select.Item value={ENTITY_COLOR_MODE} label="Entity" class={itemClass}>
              {#snippet children()}
                <Check
                  size={11}
                  class={selectedId === ENTITY_COLOR_MODE ? "text-primary" : "text-transparent"}
                />
                <span class="truncate">Entity</span>
                <span class="ml-auto shrink-0 text-[10px] text-muted-foreground">
                  One color per object
                </span>
              {/snippet}
            </Select.Item>
            {#each groups as group (group.heading)}
              <Select.Group>
                <Select.GroupHeading class={headingClass}>{group.heading}</Select.GroupHeading>
                {#each group.attributes as attribute (attribute.id)}
                  <Select.Item value={attribute.id} label={attribute.label} class={itemClass}>
                    {#snippet children()}
                      <Check
                        size={11}
                        class={selectedId === attribute.id ? "text-primary" : "text-transparent"}
                      />
                      <span class="truncate">{attribute.label}</span>
                      {#if attribute.scale === "numeric"}
                        <span class="ml-auto shrink-0 text-[10px] text-muted-foreground">
                          number
                        </span>
                      {/if}
                    {/snippet}
                  </Select.Item>
                {/each}
              </Select.Group>
            {/each}
          </Select.Content>
        </Select.Portal>
      </Select.Root>
    </div>
    {#if selectedAttribute}
      <Tooltip.Root>
        <Tooltip.Trigger
          type="button"
          onclick={() => (colorByLegendOpen.value = !colorByLegendOpen.value)}
          aria-label={legendTooltip}
          aria-expanded={colorByLegendOpen.value}
          aria-controls="color-by-legend"
          class={`h-8 w-8 shrink-0 inline-flex items-center justify-center rounded-lg border transition-colors ${
            colorByLegendOpen.value
              ? "border-primary/40 bg-primary/10 text-primary"
              : "border-border/60 bg-background text-muted-foreground hover:text-foreground hover:bg-accent"
          }`}
        >
          <Swatches class="h-4 w-4" />
        </Tooltip.Trigger>
        <TooltipContent>
          <p>{legendTooltip}</p>
        </TooltipContent>
      </Tooltip.Root>
    {/if}
  </div>
{/if}
