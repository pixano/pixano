<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Select } from "bits-ui";
  import { CaretDown, Check } from "phosphor-svelte";

  import {
    getOperatorsForType,
    type EntityFilter,
    type FieldCol,
    type FieldOperator,
  } from "$lib/types/workspace";

  interface Props {
    filter: EntityFilter;
    tableColumns: string[];
    fieldColumns: Record<string, FieldCol[]>;
  }

  let { filter = $bindable(), tableColumns, fieldColumns }: Props = $props();

  let ftype: string = $state("str");
  // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment
  let fieldOperators: FieldOperator[] = $state([]);

  const syncFieldConfig = () => {
    const tableFields = fieldColumns[filter.table] ?? [];
    if (tableFields.length === 0) return;

    if (!tableFields.find((field) => field.name === filter.name)) {
      filter.name = tableFields[0].name;
    }

    ftype = tableFields.find((field) => field.name === filter.name)?.type ?? "str";
    fieldOperators = getOperatorsForType(ftype);

    if (!fieldOperators.includes(filter.fieldOperator)) {
      filter.fieldOperator = fieldOperators[0];
    }
  };

  const handleBoolValClick = (b: boolean) => {
    filter.value = b;
  };

  const boolValue = $derived.by(() => filter.value === true || filter.value === "true");

  // Synchronize field/operator state from initial table selection
  syncFieldConfig();

  const triggerClass =
    "inline-flex h-8 items-center justify-between gap-1.5 rounded-lg border border-border/60 bg-background px-2 text-xs font-medium shadow-sm transition-colors hover:bg-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
  const contentClass =
    "z-[130] max-h-64 overflow-y-auto rounded-2xl border border-border/50 bg-popover/95 p-1.5 text-popover-foreground shadow-elevation-2 backdrop-blur-md";
  const itemClass =
    "flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-xs outline-none transition-colors data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground";
</script>

<div class="rounded-lg border border-border/40 bg-background/70 p-2 space-y-2">
  <div class="flex flex-wrap items-center gap-2">
    {#if filter.logicOperator !== "FIRST"}
      <span
        class="rounded-md bg-primary/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-primary"
      >
        {filter.logicOperator}
      </span>
    {/if}

    <Select.Root
      type="single"
      value={filter.table}
      onValueChange={(next: string) => {
        if (!next) return;
        filter.table = next;
        syncFieldConfig();
      }}
    >
      <Select.Trigger aria-label="Filter table" class={triggerClass}>
        {#snippet children()}
          <span class="truncate">{filter.table}</span>
          <CaretDown size={11} class="shrink-0 text-muted-foreground" />
        {/snippet}
      </Select.Trigger>
      <Select.Portal>
        <Select.Content sideOffset={6} class={contentClass}>
          {#each tableColumns as table (table)}
            <Select.Item value={table} label={table} class={itemClass}>
              {#snippet children()}
                <Check
                  size={11}
                  class={filter.table === table ? "text-primary" : "text-transparent"}
                />
                {table}
              {/snippet}
            </Select.Item>
          {/each}
        </Select.Content>
      </Select.Portal>
    </Select.Root>

    <Select.Root
      type="single"
      value={filter.name}
      onValueChange={(next: string) => {
        if (!next) return;
        filter.name = next;
        syncFieldConfig();
      }}
    >
      <Select.Trigger aria-label="Filter field" class={triggerClass}>
        {#snippet children()}
          <span class="truncate">{filter.name}</span>
          <CaretDown size={11} class="shrink-0 text-muted-foreground" />
        {/snippet}
      </Select.Trigger>
      <Select.Portal>
        <Select.Content sideOffset={6} class={contentClass}>
          {#each fieldColumns[filter.table] as { name } (name)}
            <Select.Item value={name} label={name} class={itemClass}>
              {#snippet children()}
                <Check
                  size={11}
                  class={filter.name === name ? "text-primary" : "text-transparent"}
                />
                {name}
              {/snippet}
            </Select.Item>
          {/each}
        </Select.Content>
      </Select.Portal>
    </Select.Root>

    <Select.Root
      type="single"
      value={filter.fieldOperator}
      onValueChange={(next) => {
        if (next) filter.fieldOperator = next as FieldOperator;
      }}
    >
      <Select.Trigger aria-label="Filter operator" class={triggerClass}>
        {#snippet children()}
          <span class="truncate">{filter.fieldOperator}</span>
          <CaretDown size={11} class="shrink-0 text-muted-foreground" />
        {/snippet}
      </Select.Trigger>
      <Select.Portal>
        <Select.Content sideOffset={6} class={contentClass}>
          {#each fieldOperators as fieldOperator (fieldOperator)}
            <Select.Item value={fieldOperator} label={fieldOperator} class={itemClass}>
              {#snippet children()}
                <Check
                  size={11}
                  class={filter.fieldOperator === fieldOperator
                    ? "text-primary"
                    : "text-transparent"}
                />
                {fieldOperator}
              {/snippet}
            </Select.Item>
          {/each}
        </Select.Content>
      </Select.Portal>
    </Select.Root>
  </div>

  {#if ftype === "bool"}
    <div class="flex items-center gap-2">
      <span class="text-[10px] uppercase tracking-wide text-muted-foreground">Value</span>
      <button
        type="button"
        onclick={() => handleBoolValClick(true)}
        class={`h-7 rounded-md px-2 text-xs font-medium border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
          boolValue
            ? "border-primary bg-primary text-primary-foreground"
            : "border-border/60 bg-background text-foreground hover:bg-accent"
        }`}
      >
        true
      </button>
      <button
        type="button"
        onclick={() => handleBoolValClick(false)}
        class={`h-7 rounded-md px-2 text-xs font-medium border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
          !boolValue
            ? "border-primary bg-primary text-primary-foreground"
            : "border-border/60 bg-background text-foreground hover:bg-accent"
        }`}
      >
        false
      </button>
    </div>
  {:else}
    <input
      type={ftype === "int" || ftype === "float" ? "number" : "text"}
      bind:value={filter.value}
      placeholder="Filter value"
      aria-label="Filter value"
      class="h-8 w-full rounded-md border border-border/60 bg-background px-2 text-xs text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    />
  {/if}
</div>
