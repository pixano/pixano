<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import {
    buildEntityFeatureInputs,
    coerceFieldValue,
    defaultFieldValue,
    isEntityFormValid,
    resolveEntityLabelField,
    suggestionsForField,
    type EntityFeatureInput,
  } from "$lib/annotations/entityFeatures.js";
  import { pickEntityLabel, type PendingEntityChoice } from "$lib/annotations/types.js";
  import type { EntityRow } from "$lib/api/annotations.js";
  import type { WorkspaceManager } from "$lib/workspace/workspaceManager.svelte.js";

  interface Props {
    manager: WorkspaceManager;
  }

  let { manager }: Props = $props();

  const NEW_ENTITY_OPTION = "new";

  const pending = $derived(manager.pendingAnnotation);
  const featureInputs = $derived(buildEntityFeatureInputs(manager.entitySchemaFields));
  const labelField = $derived(resolveEntityLabelField(manager.entitySchemaFields));

  let selectedEntityId = $state<string>(NEW_ENTITY_OPTION);
  let fieldValues = $state<Record<string, string | number | boolean>>({});

  // Start each newly drawn box with a clean form ("New entity" + default values).
  let lastPending = $state<unknown>(null);
  $effect(() => {
    if (pending === lastPending) return;
    lastPending = pending;
    selectedEntityId = NEW_ENTITY_OPTION;
    const initial: Record<string, string | number | boolean> = {};
    for (const input of featureInputs) initial[input.name] = defaultFieldValue(input.type);
    fieldValues = initial;
  });

  function shortenId(id: string): string {
    return id.length > 12 ? `${id.slice(0, 6)}…${id.slice(-4)}` : id;
  }

  function entityOptionLabel(entity: EntityRow): string {
    const label = pickEntityLabel(entity);
    return label ? `${label} (${shortenId(entity.id)})` : shortenId(entity.id);
  }

  const choice = $derived<PendingEntityChoice>(
    selectedEntityId === NEW_ENTITY_OPTION
      ? {
          mode: "new",
          entityFields: Object.fromEntries(
            featureInputs.map((input) => [
              input.name,
              coerceFieldValue(input.type, fieldValues[input.name]),
            ]),
          ),
        }
      : { mode: "existing", entityId: selectedEntityId },
  );

  const valid = $derived(isEntityFormValid(choice, labelField));

  function handleNumberInput(input: EntityFeatureInput, raw: string): void {
    fieldValues[input.name] = raw === "" ? "" : Number(raw);
  }
</script>

{#if pending}
  <div class="border-b border-border bg-muted/30 p-3">
    <h4 class="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
      Save {pending.label}
    </h4>

    <div class="flex flex-col gap-3">
      <label class="flex flex-col gap-1 text-xs">
        <span class="text-muted-foreground">Entity</span>
        <select
          bind:value={selectedEntityId}
          class="rounded-md border border-input bg-background px-2 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
        >
          <option value={NEW_ENTITY_OPTION}>New entity</option>
          {#each manager.entities as entity (entity.id)}
            <option value={entity.id}>{entityOptionLabel(entity)}</option>
          {/each}
        </select>
      </label>

      {#if selectedEntityId === NEW_ENTITY_OPTION}
        {#each featureInputs as input (input.name)}
          {#if input.type === "bool"}
            <label class="flex items-center gap-2 text-xs">
              <input
                type="checkbox"
                checked={fieldValues[input.name] === true}
                onchange={(e) => (fieldValues[input.name] = e.currentTarget.checked)}
                class="h-3.5 w-3.5 rounded border-input"
              />
              <span class="capitalize text-foreground">{input.label}</span>
            </label>
          {:else if input.type === "list"}
            <label class="flex flex-col gap-1 text-xs">
              <span class="capitalize text-muted-foreground">{input.label}</span>
              <select
                value={fieldValues[input.name]}
                onchange={(e) => (fieldValues[input.name] = e.currentTarget.value)}
                class="rounded-md border border-input bg-background px-2 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="">—</option>
                {#each input.options ?? [] as option (option)}
                  <option value={option}>{option}</option>
                {/each}
              </select>
            </label>
          {:else if input.type === "str"}
            <label class="flex flex-col gap-1 text-xs">
              <span class="capitalize text-muted-foreground">{input.label}</span>
              <input
                type="text"
                list="entity-feature-{input.name}"
                value={fieldValues[input.name]}
                oninput={(e) => (fieldValues[input.name] = e.currentTarget.value)}
                class="rounded-md border border-input bg-background px-2 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              />
              <datalist id="entity-feature-{input.name}">
                {#each suggestionsForField(manager.entities, input.name) as suggestion (suggestion)}
                  <option value={suggestion}></option>
                {/each}
              </datalist>
            </label>
          {:else}
            <label class="flex flex-col gap-1 text-xs">
              <span class="capitalize text-muted-foreground">{input.label}</span>
              <input
                type="number"
                step={input.type === "int" ? "1" : "any"}
                value={fieldValues[input.name]}
                oninput={(e) => handleNumberInput(input, e.currentTarget.value)}
                class="rounded-md border border-input bg-background px-2 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </label>
          {/if}
        {/each}
      {/if}

      <div class="flex gap-2 pt-1">
        <button
          type="button"
          onclick={() => manager.confirmPendingAnnotation(choice)}
          disabled={!valid}
          class="rounded bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Confirm
        </button>
        <button
          type="button"
          onclick={() => manager.cancelPendingAnnotation()}
          class="rounded border border-border px-2.5 py-1 text-xs hover:bg-accent"
        >
          Cancel
        </button>
      </div>
    </div>
  </div>
{/if}
