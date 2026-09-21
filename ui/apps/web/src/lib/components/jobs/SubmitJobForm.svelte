<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import SchemaField from "./SchemaField.svelte";
  import { initialValues, missingRequired, requiredNames, toParams } from "./schemaForm";
  import type { JobKind } from "$lib/api/jobs";

  type Props = {
    kinds: JobKind[];
    datasetId: string | null;
    onSubmit: (kind: string, params: Record<string, unknown>) => Promise<boolean>;
  };

  let { kinds, datasetId, onSubmit }: Props = $props();

  let selectedName = $state("");
  let values = $state<Record<string, unknown>>({});
  let submitting = $state(false);

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

  // Switching kind must not carry the previous kind's values over: the parameters are not
  // the same, and a stale one would be refused by the schema it does not belong to.
  $effect(() => {
    const schema = selected?.params_schema;
    values = schema ? initialValues(schema) : {};
  });

  async function handleSubmit(event: SubmitEvent) {
    event.preventDefault();
    if (!selected || !datasetId || submitting) return;
    submitting = true;
    const accepted = await onSubmit(selected.name, toParams(selected.params_schema, values));
    submitting = false;
    if (accepted) values = initialValues(selected.params_schema);
  }
</script>

<form class="flex flex-col gap-3 border-b border-border p-3" onsubmit={handleSubmit}>
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
      onChange={(value: unknown) => (values = { ...values, [name]: value })}
    />
  {/each}

  {#if !datasetId}
    <p class="text-xs text-muted-foreground">Open a dataset to run a job on it.</p>
  {:else if missing.length > 0}
    <p class="text-xs text-muted-foreground">Fill in: {missing.join(", ")}</p>
  {/if}

  <button
    type="submit"
    class="rounded bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground disabled:opacity-50"
    disabled={!selected || !datasetId || missing.length > 0 || submitting}
  >
    {submitting ? "Starting…" : "Run"}
  </button>
</form>
