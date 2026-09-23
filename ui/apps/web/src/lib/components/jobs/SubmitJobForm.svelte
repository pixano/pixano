<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { untrack } from "svelte";

  import SchemaField from "./SchemaField.svelte";
  import {
    confirmationsFor,
    initialValues,
    missingRequired,
    modelTaskOf,
    proposeModels,
    requiredNames,
    toParams,
    type ServedModels,
  } from "./schemaForm";
  import type { JobKind, JobTarget } from "$lib/api/jobs";

  type Props = {
    kinds: JobKind[];
    dataset: JobTarget | null;
    /** The models the inference serves, by task, for the model fields to offer. */
    servedModels: ServedModels;
    onSubmit: (kind: string, params: Record<string, unknown>) => Promise<boolean>;
  };

  let { kinds, dataset, servedModels, onSubmit }: Props = $props();

  let selectedName = $state("");
  let values = $state<Record<string, unknown>>({});
  let submitting = $state(false);
  // Set by a first click when a parameter asks for confirmation; any edit clears it, so what
  // is confirmed is what runs.
  let confirming = $state(false);

  const selected = $derived(kinds.find((kind) => kind.name === selectedName) ?? kinds[0]);

  // The kinds arrive from the backend, so the selection cannot be seeded at construction:
  // it would capture an empty list. It is also re-seeded if the chosen kind disappears —
  // a worker can be redeployed with a different registry while the panel is open.
  $effect(() => {
    if (kinds.length > 0 && !kinds.some((kind) => kind.name === selectedName)) {
      selectedName = kinds[0].name;
    }
  });
  const required = $derived(selected ? requiredNames(selected.params_schema) : new Set<string>());
  const missing = $derived(selected ? missingRequired(selected.params_schema, values) : []);
  const fields = $derived(Object.entries(selected?.params_schema.properties ?? {}));
  const confirmations = $derived(selected ? confirmationsFor(selected.params_schema, values) : []);

  // Switching kind must not carry the previous kind's values over: the parameters are not
  // the same, and a stale one would be refused by the schema it does not belong to.
  $effect(() => {
    const schema = selected?.params_schema;
    values = schema
      ? proposeModels(
          schema,
          initialValues(schema),
          untrack(() => servedModels),
        )
      : {};
    confirming = false;
  });

  // The served models arrive after the form is drawn: fill the model fields still empty then,
  // without touching one the user already set.
  $effect(() => {
    const schema = untrack(() => selected?.params_schema);
    const served = servedModels;
    if (schema)
      values = proposeModels(
        schema,
        untrack(() => values),
        served,
      );
  });

  async function handleSubmit(event: SubmitEvent) {
    event.preventDefault();
    if (!selected || !dataset || submitting) return;
    if (confirmations.length > 0 && !confirming) {
      confirming = true;
      return;
    }
    confirming = false;
    submitting = true;
    const accepted = await onSubmit(selected.name, toParams(selected.params_schema, values));
    submitting = false;
    if (accepted)
      values = proposeModels(
        selected.params_schema,
        initialValues(selected.params_schema),
        servedModels,
      );
  }
</script>

<form class="flex flex-col gap-3 border-b border-border p-3" onsubmit={handleSubmit}>
  <!--
    Named before anything else: a job runs on the dataset last opened in the Explorer, and
    nothing else on this form says which one that is.
  -->
  <div class="flex flex-col gap-1 text-sm">
    <span class="font-medium">Dataset</span>
    {#if dataset}
      <span class="truncate rounded bg-muted px-2 py-1" title={dataset.name}>{dataset.name}</span>
    {:else}
      <span class="text-xs text-muted-foreground">
        None — open a dataset in the Explorer to run a job on it.
      </span>
    {/if}
  </div>

  <label class="flex flex-col gap-1 text-sm">
    <span class="font-medium">Processing</span>
    <select
      class="rounded border border-input bg-background px-2 py-1"
      bind:value={selectedName}
      disabled={kinds.length === 0}
    >
      {#each kinds as kind (kind.name)}
        <option value={kind.name}>{kind.name}</option>
      {/each}
    </select>
  </label>

  {#each fields as [name, schema] (name)}
    <SchemaField
      {name}
      {schema}
      required={required.has(name)}
      value={values[name]}
      models={servedModels[modelTaskOf(schema) ?? ""]}
      onChange={(value: unknown) => {
        values = { ...values, [name]: value };
        confirming = false;
      }}
    />
  {/each}

  {#if dataset && missing.length > 0}
    <p class="text-xs text-muted-foreground">Fill in: {missing.join(", ")}</p>
  {/if}

  {#if confirming}
    <div
      class="flex flex-col gap-1 rounded border border-destructive/50 bg-destructive/10 p-2 text-xs"
      aria-live="polite"
    >
      {#each confirmations as text (text)}
        <p>{text}</p>
      {/each}
      <p class="font-medium">Click again to confirm.</p>
    </div>
  {/if}
  <button
    type="submit"
    class="rounded bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground disabled:opacity-50"
    disabled={!selected || !dataset || missing.length > 0 || submitting}
  >
    {submitting ? "Starting…" : confirming ? "Confirm and run" : "Run"}
  </button>
</form>
