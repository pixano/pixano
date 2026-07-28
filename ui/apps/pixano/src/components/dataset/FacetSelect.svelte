<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { CaretDown, Check } from "phosphor-svelte";

  import { Select } from "$lib/ui";
  import { cn } from "$lib/utils/styleUtils";

  interface FacetValue {
    value: string;
    count?: number;
  }

  interface Props {
    /** Facet label, e.g. "Split" or "Status". */
    label: string;
    values: FacetValue[];
    /** Currently selected facet values. */
    selected: string[];
    onChange: (values: string[]) => void;
  }

  let { label, values, selected, onChange }: Props = $props();

  let isOpen = $state(false);

  const items = $derived(values.map((v) => ({ value: v.value, label: v.value })));
  const active = $derived(selected.length > 0);
</script>

<Select.Root
  type="multiple"
  value={selected}
  {items}
  open={isOpen}
  onOpenChange={(open) => (isOpen = open)}
  onValueChange={(value) => onChange(value ?? [])}
>
  <Select.Trigger
    aria-label="{label} facet"
    class={cn(
      "inline-flex h-10 items-center gap-2 px-3.5 rounded-xl border bg-background text-xs font-bold uppercase tracking-wider shadow-sm transition-colors",
      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
      active
        ? "border-primary/40 text-foreground"
        : "border-border text-muted-foreground hover:text-foreground",
    )}
  >
    {#snippet children()}
      <span>{label}</span>
      {#if active}
        <span class="px-1.5 rounded-full bg-primary/10 text-primary tabular-nums normal-case">
          {selected.length}
        </span>
      {/if}
      <CaretDown
        size={12}
        class={cn("shrink-0 text-muted-foreground transition-transform duration-200", {
          "rotate-180": isOpen,
        })}
      />
    {/snippet}
  </Select.Trigger>

  {#if values.length > 0}
    <Select.Portal>
      <Select.Content
        sideOffset={8}
        class="z-50 min-w-[12rem] overflow-hidden rounded-2xl border border-border/50 bg-popover/95 p-1.5 text-popover-foreground shadow-elevation-2 backdrop-blur-md"
      >
        {#each values as facet (facet.value)}
          {@const isSelected = selected.includes(facet.value)}
          <Select.Item
            value={facet.value}
            label={facet.value}
            class="cursor-pointer rounded-lg px-2.5 py-2 outline-none transition-colors data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground"
          >
            {#snippet children()}
              <div class="flex items-center gap-2.5 w-full">
                <div
                  class={cn(
                    "flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors",
                    isSelected
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border bg-background",
                  )}
                >
                  {#if isSelected}
                    <Check size={10} weight="bold" />
                  {/if}
                </div>
                <span class="flex-1 truncate text-sm">{facet.value}</span>
                {#if facet.count !== undefined}
                  <span class="text-xs text-muted-foreground tabular-nums">
                    {facet.count.toLocaleString()}
                  </span>
                {/if}
              </div>
            {/snippet}
          </Select.Item>
        {/each}
      </Select.Content>
    </Select.Portal>
  {/if}
</Select.Root>
