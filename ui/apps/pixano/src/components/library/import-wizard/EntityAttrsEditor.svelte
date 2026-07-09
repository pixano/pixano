<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Plus, Trash } from "phosphor-svelte";

  import { ENTITY_ATTR_TYPES, type EntityAttrRow } from "./rawSchema";

  interface Props {
    rows: EntityAttrRow[];
  }

  let { rows = $bindable() }: Props = $props();

  function addRow() {
    rows = [...rows, { name: "", type: "str", list: false, required: false, defaultValue: "" }];
  }

  function removeRow(index: number) {
    rows = rows.filter((_, i) => i !== index);
  }

  const inputClass =
    "rounded-lg border border-border bg-card px-2 py-1.5 text-xs text-foreground " +
    "placeholder:text-muted-foreground/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
</script>

<div class="space-y-2">
  <p class="text-xs text-muted-foreground">
    Attributes each annotated object carries (e.g. <span class="font-mono">category: str</span>
    ).
  </p>

  {#each rows as row, index (index)}
    <div class="flex flex-wrap items-center gap-2">
      <input
        type="text"
        class="{inputClass} w-36 font-mono"
        placeholder="attribute_name"
        bind:value={row.name}
        aria-label="Attribute name"
      />
      <select class={inputClass} bind:value={row.type} aria-label="Attribute type">
        {#each ENTITY_ATTR_TYPES as type (type)}
          <option value={type}>{type}</option>
        {/each}
      </select>
      <label class="flex items-center gap-1 text-xs text-muted-foreground">
        <input type="checkbox" bind:checked={row.list} />
        list
      </label>
      <label class="flex items-center gap-1 text-xs text-muted-foreground">
        <input type="checkbox" bind:checked={row.required} />
        required
      </label>
      {#if !row.required}
        <input
          type="text"
          class="{inputClass} w-24 font-mono"
          placeholder="default"
          bind:value={row.defaultValue}
          aria-label="Default value"
        />
      {/if}
      <button
        type="button"
        class="text-muted-foreground hover:text-destructive"
        onclick={() => removeRow(index)}
        aria-label="Remove attribute"
      >
        <Trash weight="regular" class="h-4 w-4" />
      </button>
    </div>
  {/each}

  <button
    type="button"
    class="flex items-center gap-1.5 text-xs font-medium text-primary hover:underline"
    onclick={addRow}
  >
    <Plus weight="bold" class="h-3.5 w-3.5" />
    Add attribute
  </button>
</div>
