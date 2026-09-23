<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { CaretDown, Plus, Trash } from "phosphor-svelte";
  import { tick } from "svelte";

  import { ATTR_TYPE_LABELS, ATTR_TYPES, validateAttrRows, type AttrRow } from "./rawSchema";
  import {
    WIZARD_GHOST_BUTTON_CLASS,
    WIZARD_ICON_BUTTON_CLASS,
    WIZARD_INPUT_CLASS,
    WIZARD_SECONDARY_BUTTON_CLASS,
  } from "./wizardStyles";
  import { cn } from "$lib/utils/styleUtils";

  interface Props {
    rows: AttrRow[];
    hint: string;
    /** Imported records have no custom values yet, so their attrs must be optional. */
    allowRequired?: boolean;
  }

  let { rows = $bindable(), hint, allowRequired = true }: Props = $props();
  let editorElement = $state<HTMLDivElement | null>(null);
  let addButton = $state<HTMLButtonElement | null>(null);
  let expandedRows = $state<AttrRow[]>([]);
  // The installed ESLint parser predates this Svelte rune; svelte-check verifies its string type.
  // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment, @typescript-eslint/no-unsafe-call
  const editorId = $props.id();
  const rowErrors = $derived(
    rows.map((row) => {
      const nameError =
        validateAttrRows([{ ...row, defaultValue: "" }]) ||
        (rows.filter((other) => other.name === row.name).length > 1
          ? "Attribute '" + row.name + "' is declared twice."
          : "");
      return { name: nameError, default: nameError ? "" : validateAttrRows([row]) };
    }),
  );

  async function addRow() {
    rows = [...rows, { name: "", type: "str", list: false, required: false, defaultValue: "" }];
    await tick();
    const names = editorElement?.querySelectorAll<HTMLInputElement>("[data-attribute-name]");
    names?.item(names.length - 1)?.focus();
  }

  async function removeRow(index: number) {
    const removed = rows[index];
    rows = rows.filter((_, i) => i !== index);
    expandedRows = expandedRows.filter((row) => row !== removed);
    await tick();
    const names = editorElement?.querySelectorAll<HTMLInputElement>("[data-attribute-name]");
    const next = names?.item(Math.min(index, names.length - 1));
    (next ?? addButton)?.focus();
  }

  function toggleOptions(row: AttrRow) {
    expandedRows = expandedRows.includes(row)
      ? expandedRows.filter((expanded) => expanded !== row)
      : [...expandedRows, row];
  }

  function optionsSummary(row: AttrRow): string {
    return [
      row.required ? "Required" : "Optional",
      row.list ? "Multiple values" : "Single value",
      row.defaultValue.trim() ? "Default: " + row.defaultValue : "",
    ]
      .filter(Boolean)
      .join(" · ");
  }

  const ZERO_DEFAULTS = {
    str: '""',
    int: "0",
    float: "0",
    bool: "false",
  };
  const inputClass = cn(
    WIZARD_INPUT_CLASS,
    "h-9 min-w-0 px-2.5 text-[13px] aria-invalid:border-destructive",
  );
</script>

<div class="attrs-editor space-y-3" bind:this={editorElement}>
  <div class="editor-intro flex items-start justify-between gap-3">
    <p class="min-w-0 text-xs leading-5 text-muted-foreground">{hint}</p>
    <button
      type="button"
      class={cn(WIZARD_SECONDARY_BUTTON_CLASS, "h-9 shrink-0 gap-1.5 px-2.5 text-xs")}
      bind:this={addButton}
      onclick={() => void addRow()}
    >
      <Plus weight="bold" class="h-3.5 w-3.5" />
      Add attribute
    </button>
  </div>

  {#if rows.length}
    <div class="attribute-table overflow-hidden rounded-xl border border-border/70 bg-card">
      <div class="attribute-header" aria-hidden="true">
        <span>Name</span>
        <span>Type</span>
        <span>Options</span>
        <span class="text-center">Remove</span>
      </div>
      {#each rows as row, index (index)}
        {@const error = rowErrors[index]}
        {@const nameErrorId = editorId + "-" + index + "-name-error"}
        {@const defaultErrorId = editorId + "-" + index + "-default-error"}
        {@const defaultHintId = editorId + "-" + index + "-default-hint"}
        {@const optionsId = editorId + "-" + index + "-options"}
        {@const expanded = expandedRows.includes(row)}
        <div class="attribute-row" role="group" aria-label={row.name || "New attribute"}>
          <div class="attribute-main">
            <label class="attribute-name min-w-0">
              <span class="field-label">Name</span>
              <input
                type="text"
                class={inputClass}
                placeholder="e.g. category"
                bind:value={row.name}
                aria-label="Attribute name"
                aria-invalid={!!error.name}
                aria-describedby={editorId + "-name-hint" + (error.name ? " " + nameErrorId : "")}
                data-attribute-name
              />
            </label>
            <label class="attribute-type min-w-0">
              <span class="field-label">Type</span>
              <select class={inputClass} bind:value={row.type} aria-label="Attribute type">
                {#each ATTR_TYPES as type (type)}
                  <option value={type}>{ATTR_TYPE_LABELS[type]}</option>
                {/each}
              </select>
            </label>
            <button
              type="button"
              class={cn(
                WIZARD_GHOST_BUTTON_CLASS,
                "attribute-options h-9 justify-start gap-1.5 px-2 text-xs",
                expanded && "bg-surface-2 text-foreground",
              )}
              aria-expanded={expanded}
              aria-controls={optionsId}
              aria-label={"Options for " + (row.name || "attribute " + (index + 1))}
              title={optionsSummary(row)}
              onclick={() => toggleOptions(row)}
            >
              Options
              <CaretDown class={cn("h-3.5 w-3.5 transition-transform", expanded && "rotate-180")} />
            </button>
            <button
              type="button"
              class={cn(
                WIZARD_ICON_BUTTON_CLASS,
                "attribute-remove h-9 w-9 justify-self-center hover:bg-destructive/5 hover:text-destructive",
              )}
              onclick={() => void removeRow(index)}
              aria-label={row.name ? "Remove attribute " + row.name : "Remove attribute"}
            >
              <Trash weight="regular" class="h-4 w-4" />
            </button>
          </div>
          {#if error.name}
            <p id={nameErrorId} class="px-3 pb-2 text-xs text-destructive" role="alert">
              {error.name}
            </p>
          {/if}

          {#if expanded}
            <div
              id={optionsId}
              class="attribute-details border-t border-border/60 bg-surface-2/60 p-3"
            >
              <div class="space-y-3">
                <label class="flex items-center gap-2 text-xs text-foreground">
                  <input
                    type="checkbox"
                    class="h-3.5 w-3.5 accent-primary"
                    bind:checked={row.list}
                  />
                  Multiple values
                </label>
                {#if allowRequired}
                  <label class="flex items-center gap-2 text-xs text-foreground">
                    <input
                      type="checkbox"
                      class="h-3.5 w-3.5 accent-primary"
                      checked={row.required}
                      onchange={(event) => {
                        row.required = event.currentTarget.checked;
                        if (row.required) row.defaultValue = "";
                      }}
                    />
                    Required when annotating
                  </label>
                {/if}
              </div>
              {#if !row.required}
                <div class="min-w-0 space-y-1.5">
                  <label class="block space-y-1.5">
                    <span class="text-xs font-medium text-foreground">
                      Default value (optional)
                    </span>
                    <input
                      type="text"
                      class={inputClass}
                      placeholder={row.list
                        ? "e.g. cup, bottle"
                        : row.type === "bool"
                          ? "true or false"
                          : "Standard default"}
                      bind:value={row.defaultValue}
                      aria-label="Default value"
                      aria-invalid={!!error.default}
                      aria-describedby={defaultHintId + (error.default ? " " + defaultErrorId : "")}
                    />
                  </label>
                  <p id={defaultHintId} class="text-[11px] leading-4 text-muted-foreground">
                    {#if row.list}
                      Comma-separated values; [] if unset.
                    {:else}
                      {ZERO_DEFAULTS[row.type]} if unset.
                    {/if}
                  </p>
                </div>
              {:else}
                <p class="text-xs leading-5 text-muted-foreground">
                  Required attributes have no default.
                </p>
              {/if}
            </div>
          {/if}
          {#if error.default}
            <p id={defaultErrorId} class="px-3 py-2 text-xs text-destructive" role="alert">
              {error.default}
            </p>
          {/if}
        </div>
      {/each}
    </div>
    <p id={editorId + "-name-hint"} class="text-[11px] leading-4 text-muted-foreground">
      Names: snake_case, e.g. object_category.
    </p>
  {/if}
</div>

<style>
  .attrs-editor {
    container: attributes / inline-size;
  }

  .attribute-header {
    display: none;
  }

  .attribute-row + .attribute-row {
    border-top: 1px solid var(--color-border);
  }

  .attribute-main {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 2.5rem;
    align-items: end;
    gap: 0.75rem;
    padding: 0.75rem;
  }

  .attribute-name {
    grid-column: 1;
    grid-row: 1;
  }

  .attribute-type {
    grid-column: 1;
    grid-row: 2;
  }

  .attribute-options {
    grid-column: 1;
    grid-row: 3;
    justify-self: start;
  }

  .attribute-remove {
    grid-column: 2;
    grid-row: 1;
  }

  .field-label {
    display: block;
    margin-bottom: 0.375rem;
    font-size: 0.75rem;
    font-weight: 500;
  }

  .attribute-details {
    display: grid;
    gap: 1rem;
  }

  @container attributes (max-width: 359px) {
    .editor-intro {
      flex-direction: column;
      gap: 0.5rem;
    }
  }

  @container attributes (min-width: 500px) {
    .attribute-header,
    .attribute-main {
      grid-template-columns: minmax(0, 1fr) 9.25rem 5.25rem 2.5rem;
      gap: 0.5rem;
      padding: 0.625rem 0.75rem;
    }

    .attribute-header {
      display: grid;
      border-bottom: 1px solid var(--color-border);
      background: var(--color-surface-2);
      color: var(--color-muted-foreground);
      font-size: 0.6875rem;
      font-weight: 500;
    }

    .attribute-main {
      align-items: center;
    }

    .attribute-type {
      grid-column: 2;
      grid-row: 1;
    }

    .attribute-options {
      grid-column: 3;
      grid-row: 1;
    }

    .attribute-remove {
      grid-column: 4;
      grid-row: 1;
    }

    .field-label {
      display: none;
    }

    .attribute-details {
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      align-items: start;
    }
  }
</style>
