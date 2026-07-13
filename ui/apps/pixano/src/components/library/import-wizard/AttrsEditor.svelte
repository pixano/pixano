<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Plus, Trash } from "phosphor-svelte";

  import { ATTR_TYPES, type AttrRow } from "./rawSchema";

  interface Props {
    rows: AttrRow[];
    hint: string;
    /** Record attrs forbid `required`: media-only imports create records with no attr values. */
    allowRequired?: boolean;
  }

  let { rows = $bindable(), hint, allowRequired = true }: Props = $props();

  function addRow() {
    rows = [...rows, { name: "", type: "str", list: false, required: false, defaultValue: "" }];
  }

  function removeRow(index: number) {
    rows = rows.filter((_, i) => i !== index);
  }

  const ZERO_DEFAULTS: Record<string, string> = {
    str: '""',
    int: "0",
    float: "0.0",
    bool: "false",
  };

  const inputClass =
    "rounded-lg border border-border bg-card px-2 py-1.5 text-xs text-foreground " +
    "placeholder:text-muted-foreground/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
</script>

<div class="space-y-2">
  <p class="text-xs text-muted-foreground">{hint}</p>

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
        {#each ATTR_TYPES as type (type)}
          <option value={type}>{type}</option>
        {/each}
      </select>
      <label class="flex items-center gap-1 text-xs text-muted-foreground">
        <input type="checkbox" bind:checked={row.list} />
        list
      </label>
      {#if allowRequired}
        <label class="flex items-center gap-1 text-xs text-muted-foreground">
          <input type="checkbox" bind:checked={row.required} />
          required
        </label>
      {/if}
      {#if !row.required}
        <input
          type="text"
          class="{inputClass} w-28 font-mono"
          placeholder={row.list ? "a, b, c" : "default"}
          bind:value={row.defaultValue}
          aria-label="Default value"
        />
        {#if !row.defaultValue.trim()}
          <span class="text-[10px] text-muted-foreground/70">
            defaults to {row.list ? "[]" : ZERO_DEFAULTS[row.type]}
          </span>
        {/if}
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
