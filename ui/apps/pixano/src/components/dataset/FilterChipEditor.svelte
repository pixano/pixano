<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Check, X } from "phosphor-svelte";
  import { untrack } from "svelte";

  import type { ColumnDescriptorResponse } from "$lib/api/restTypes";
  import { IconButton } from "$lib/ui";
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
    const wanted = isBetween ? 2 : listMode ? Math.max(values.length, 1) : 1;
    if (!listMode && values.length !== 1) values = [values[0] ?? ""];
    else if (isBetween && values.length !== 2) values = [values[0] ?? "", values[1] ?? ""];
    else if (listMode && !isBetween && values.length < 1) values = [""];
    void wanted;
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
</script>

<div
  class="flex flex-wrap items-center gap-2 p-2 rounded-lg border border-border bg-card shadow-sm"
>
  <select bind:value={col} class="h-9 rounded-md border border-border bg-background px-2 text-sm">
    {#each filterable as c (c.name)}
      <option value={c.name}>{c.name}</option>
    {/each}
  </select>

  <select bind:value={op} class="h-9 rounded-md border border-border bg-background px-2 text-sm">
    {#each operators as o (o)}
      <option value={o}>{OPERATOR_LABELS[o] ?? o}</option>
    {/each}
  </select>

  {#if enumValues && !listMode}
    <select
      bind:value={values[0]}
      class="h-9 rounded-md border border-border bg-background px-2 text-sm"
    >
      <option value="" disabled>Select…</option>
      {#each enumValues as v (v)}
        <option value={v}>{v}</option>
      {/each}
    </select>
  {:else if isBetween}
    <input
      type={inputType()}
      bind:value={values[0]}
      placeholder="from"
      class="h-9 w-36 rounded-md border border-border bg-background px-2 text-sm"
    />
    <span class="text-muted-foreground text-sm">and</span>
    <input
      type={inputType()}
      bind:value={values[1]}
      placeholder="to"
      class="h-9 w-36 rounded-md border border-border bg-background px-2 text-sm"
    />
  {:else if listMode}
    <div class="flex flex-wrap items-center gap-1">
      {#each values as value, i (i)}
        <div class="flex items-center gap-1">
          {#if enumValues}
            <select
              {value}
              onchange={(e) => (values[i] = e.currentTarget.value)}
              class="h-9 rounded-md border border-border bg-background px-2 text-sm"
            >
              <option value="" disabled>Select…</option>
              {#each enumValues as v (v)}
                <option value={v}>{v}</option>
              {/each}
            </select>
          {:else}
            <input
              type={inputType()}
              {value}
              oninput={(e) => (values[i] = e.currentTarget.value)}
              placeholder="value"
              class="h-9 w-32 rounded-md border border-border bg-background px-2 text-sm"
            />
          {/if}
          {#if values.length > 1}
            <button
              type="button"
              onclick={() => removeValueSlot(i)}
              aria-label="Remove value"
              class="p-1 rounded hover:bg-accent text-muted-foreground"
            >
              <X size={14} />
            </button>
          {/if}
        </div>
      {/each}
      <button
        type="button"
        onclick={addValueSlot}
        class="h-9 px-2 rounded-md border border-dashed border-border text-xs text-muted-foreground hover:bg-accent"
      >
        + value
      </button>
    </div>
  {:else}
    <input
      type={inputType()}
      bind:value={values[0]}
      placeholder="value"
      onkeydown={(e) => e.key === "Enter" && save()}
      class="h-9 w-44 rounded-md border border-border bg-background px-2 text-sm"
    />
  {/if}

  <div class="flex items-center gap-1 ml-auto">
    <IconButton onclick={save} disabled={!canSave} tooltipContent="Apply filter">
      <Check weight="bold" />
    </IconButton>
    <IconButton onclick={onCancel} tooltipContent="Cancel">
      <X weight="bold" />
    </IconButton>
  </div>
</div>
