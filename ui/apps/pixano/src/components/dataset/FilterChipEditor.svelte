<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { CaretUpDown, Check, X } from "phosphor-svelte";
  import { untrack } from "svelte";

  import type { ColumnDescriptorResponse } from "$lib/api/restTypes";
  import { Select } from "$lib/ui";
  import { formatColumnLabel } from "$lib/utils/columns";
  import { isListOperator, OPERATOR_LABELS, type RecordFilter } from "$lib/utils/recordFilters";

  interface Props {
    columns: ColumnDescriptorResponse[];
    /** Filter to edit; when omitted the editor starts blank (add mode). */
    initial?: RecordFilter;
    onSave: (filter: RecordFilter) => void;
    onCancel: () => void;
  }

  let { columns, initial, onSave, onCancel }: Props = $props();

  const filterable = $derived(columns.filter((c) => c.filterable));

  // Seed from the (optional) initial filter once; the component is remounted by
  // its parent (keyed on the edit target) when a different filter is edited.
  let col = $state(untrack(() => initial?.col ?? filterable[0]?.name ?? ""));
  let op = $state(untrack(() => initial?.op ?? ""));
  let values = $state<string[]>(untrack(() => (initial ? [...initial.values] : [""])));

  const column = $derived(filterable.find((c) => c.name === col));
  const operators = $derived(column?.operators ?? []);
  const listMode = $derived(isListOperator(op));
  const isBetween = $derived(op === "between");
  const enumValues = $derived(column?.values ?? null);

  // Keep the operator valid for the selected column.
  $effect(() => {
    if (operators.length > 0 && !operators.includes(op)) {
      op = operators[0];
    }
  });

  // Normalize the value slots to the operator's arity.
  $effect(() => {
    if (!listMode && values.length !== 1) values = [values[0] ?? ""];
    else if (isBetween && values.length !== 2) values = [values[0] ?? "", values[1] ?? ""];
    else if (listMode && !isBetween && values.length < 1) values = [""];
  });

  const canSave = $derived(
    col !== "" &&
      op !== "" &&
      values.some((v) => v.trim() !== "") &&
      (!isBetween || values.every((v) => v !== "")),
  );

  function inputType(): "text" | "number" | "date" {
    if (column?.type === "datetime") return "date";
    if (column?.type === "int" || column?.type === "float") return "number";
    return "text";
  }

  function addValueSlot() {
    values = [...values, ""];
  }

  function removeValueSlot(index: number) {
    values = values.filter((_, i) => i !== index);
    if (values.length === 0) values = [""];
  }

  function save() {
    if (!canSave) return;
    onSave({ col, op, values: values.map((v) => v.trim()).filter((v) => v !== "") });
  }

  function handleContainerKeydown(event: KeyboardEvent) {
    if (event.key === "Escape") {
      event.stopPropagation();
      onCancel();
    } else if (event.key === "Enter" && canSave) {
      // Selects handle Enter themselves while open; this catches the rest of the form.
      const target = event.target as HTMLElement;
      if (target.closest("[data-select-content]") === null) {
        event.preventDefault();
        save();
      }
    }
  }

  const triggerClass =
    "inline-flex h-9 items-center justify-between gap-2 px-3 rounded-xl border border-input bg-background text-sm shadow-sm transition-colors hover:bg-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
  const contentClass =
    "z-50 min-w-[10rem] max-h-72 overflow-y-auto rounded-2xl border border-border/50 bg-popover/95 p-1.5 text-popover-foreground shadow-elevation-2 backdrop-blur-md";
  const itemClass =
    "cursor-pointer rounded-lg px-2.5 py-1.5 text-sm outline-none transition-colors data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground";
  const inputClass =
    "h-9 rounded-xl border border-input bg-background px-3 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-primary/20";
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="flex flex-wrap items-center gap-2 p-2.5 rounded-xl border border-border bg-card shadow-elevation-1"
  onkeydown={handleContainerKeydown}
>
  <!-- Column -->
  <Select.Root
    type="single"
    value={col}
    items={filterable.map((c) => ({ value: c.name, label: formatColumnLabel(c.name) }))}
    onValueChange={(value: string) => {
      if (value) col = value;
    }}
  >
    <Select.Trigger aria-label="Filter column" class={triggerClass}>
      {#snippet children()}
        <span class="truncate">{col ? formatColumnLabel(col) : "Column"}</span>
        <CaretUpDown size={13} class="shrink-0 text-muted-foreground" />
      {/snippet}
    </Select.Trigger>
    <Select.Portal>
      <Select.Content sideOffset={6} class={contentClass} data-select-content>
        {#each filterable as c (c.name)}
          <Select.Item value={c.name} label={formatColumnLabel(c.name)} class={itemClass}>
            {#snippet children()}
              <span class="flex items-center gap-2">
                {#if col === c.name}<Check size={12} class="text-primary" />{/if}
                {formatColumnLabel(c.name)}
              </span>
            {/snippet}
          </Select.Item>
        {/each}
      </Select.Content>
    </Select.Portal>
  </Select.Root>

  <!-- Operator -->
  <Select.Root
    type="single"
    value={op}
    items={operators.map((o) => ({ value: o, label: OPERATOR_LABELS[o] ?? o }))}
    onValueChange={(value: string) => {
      if (value) op = value;
    }}
  >
    <Select.Trigger aria-label="Filter operator" class={triggerClass}>
      {#snippet children()}
        <span class="truncate">{OPERATOR_LABELS[op] ?? op ?? "Operator"}</span>
        <CaretUpDown size={13} class="shrink-0 text-muted-foreground" />
      {/snippet}
    </Select.Trigger>
    <Select.Portal>
      <Select.Content sideOffset={6} class={contentClass} data-select-content>
        {#each operators as o (o)}
          <Select.Item value={o} label={OPERATOR_LABELS[o] ?? o} class={itemClass}>
            {#snippet children()}
              <span class="flex items-center gap-2">
                {#if op === o}<Check size={12} class="text-primary" />{/if}
                {OPERATOR_LABELS[o] ?? o}
              </span>
            {/snippet}
          </Select.Item>
        {/each}
      </Select.Content>
    </Select.Portal>
  </Select.Root>

  <!-- Value(s) -->
  {#if enumValues && !listMode}
    <Select.Root
      type="single"
      value={values[0]}
      items={enumValues.map((v) => ({ value: v, label: v }))}
      onValueChange={(value: string) => {
        if (value) values[0] = value;
      }}
    >
      <Select.Trigger aria-label="Filter value" class={triggerClass}>
        {#snippet children()}
          <span class="truncate">{values[0] || "Select…"}</span>
          <CaretUpDown size={13} class="shrink-0 text-muted-foreground" />
        {/snippet}
      </Select.Trigger>
      <Select.Portal>
        <Select.Content sideOffset={6} class={contentClass} data-select-content>
          {#each enumValues as v (v)}
            <Select.Item value={v} label={v} class={itemClass}>
              {#snippet children()}
                <span class="flex items-center gap-2">
                  {#if values[0] === v}<Check size={12} class="text-primary" />{/if}
                  {v}
                </span>
              {/snippet}
            </Select.Item>
          {/each}
        </Select.Content>
      </Select.Portal>
    </Select.Root>
  {:else if isBetween}
    <input type={inputType()} bind:value={values[0]} placeholder="from" class="{inputClass} w-36" />
    <span class="text-muted-foreground text-sm">and</span>
    <input type={inputType()} bind:value={values[1]} placeholder="to" class="{inputClass} w-36" />
  {:else if listMode}
    <div class="flex flex-wrap items-center gap-1.5">
      {#each values as value, i (i)}
        <div class="flex items-center gap-1">
          {#if enumValues}
            <Select.Root
              type="single"
              {value}
              items={enumValues.map((v) => ({ value: v, label: v }))}
              onValueChange={(next: string) => {
                if (next) values[i] = next;
              }}
            >
              <Select.Trigger aria-label="Filter value {i + 1}" class={triggerClass}>
                {#snippet children()}
                  <span class="truncate">{value || "Select…"}</span>
                  <CaretUpDown size={13} class="shrink-0 text-muted-foreground" />
                {/snippet}
              </Select.Trigger>
              <Select.Portal>
                <Select.Content sideOffset={6} class={contentClass} data-select-content>
                  {#each enumValues as v (v)}
                    <Select.Item value={v} label={v} class={itemClass}>
                      {#snippet children()}
                        <span class="flex items-center gap-2">
                          {#if value === v}<Check size={12} class="text-primary" />{/if}
                          {v}
                        </span>
                      {/snippet}
                    </Select.Item>
                  {/each}
                </Select.Content>
              </Select.Portal>
            </Select.Root>
          {:else}
            <input
              type={inputType()}
              {value}
              oninput={(e) => (values[i] = e.currentTarget.value)}
              placeholder="value"
              class="{inputClass} w-32"
            />
          {/if}
          {#if values.length > 1}
            <button
              type="button"
              onclick={() => removeValueSlot(i)}
              aria-label="Remove value"
              class="p-1 rounded-md hover:bg-accent text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <X size={14} />
            </button>
          {/if}
        </div>
      {/each}
      <button
        type="button"
        onclick={addValueSlot}
        class="h-9 px-2.5 rounded-xl border border-dashed border-border text-xs text-muted-foreground hover:bg-accent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        + value
      </button>
    </div>
  {:else}
    <!-- svelte-ignore a11y_autofocus -->
    <input
      type={inputType()}
      bind:value={values[0]}
      placeholder="value"
      autofocus
      class="{inputClass} w-44"
    />
  {/if}

  <div class="flex items-center gap-2 ml-auto">
    <button
      type="button"
      onclick={onCancel}
      class="h-9 px-3.5 rounded-xl text-xs font-bold uppercase tracking-wider text-muted-foreground hover:bg-accent hover:text-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      Cancel
    </button>
    <button
      type="button"
      onclick={save}
      disabled={!canSave}
      class="h-9 px-3.5 rounded-xl bg-primary text-primary-foreground text-xs font-bold uppercase tracking-wider shadow-sm hover:bg-primary/90 active:scale-95 transition-all disabled:opacity-50 disabled:pointer-events-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
    >
      Apply
    </button>
  </div>
</div>
