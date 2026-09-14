<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { asText, fieldKind, type FieldKind } from "./schemaForm";
  import type { JsonSchema } from "$lib/api/jobs";

  type Props = {
    name: string;
    schema: JsonSchema;
    required: boolean;
    value: unknown;
    onChange: (value: unknown) => void;
  };

  let { name, schema, required, value, onChange }: Props = $props();

  const kind: FieldKind = $derived(fieldKind(schema));
  const label = $derived(schema.title ?? name);
</script>

<label class="flex flex-col gap-1 text-sm">
  <span class="font-medium">
    {label}
    {#if required}<span class="text-destructive" title="Required">*</span>{/if}
  </span>

  {#if kind === "boolean"}
    <input
      type="checkbox"
      class="h-4 w-4 self-start"
      checked={Boolean(value)}
      onchange={(event) => onChange(event.currentTarget.checked)}
    />
  {:else if kind === "enum"}
    <select
      class="rounded border border-input bg-background px-2 py-1"
      value={asText(value)}
      onchange={(event) => onChange(event.currentTarget.value)}
    >
      {#each schema.enum ?? [] as option (asText(option))}
        <option value={asText(option)}>{asText(option)}</option>
      {/each}
    </select>
  {:else if kind === "number" || kind === "integer"}
    <input
      type="number"
      class="rounded border border-input bg-background px-2 py-1"
      step={kind === "integer" ? 1 : "any"}
      min={schema.minimum}
      max={schema.maximum}
      value={asText(value)}
      onchange={(event) => onChange(event.currentTarget.value)}
    />
  {:else if kind === "string"}
    <input
      type="text"
      class="rounded border border-input bg-background px-2 py-1"
      value={asText(value)}
      onchange={(event) => onChange(event.currentTarget.value)}
    />
  {:else}
    <!--
      Shown rather than hidden on purpose: silently dropping a parameter the form cannot
      render would submit a job the user did not describe, and a required one would be
      refused with no visible cause.
    -->
    <span class="rounded border border-dashed border-muted-foreground/50 px-2 py-1 text-xs">
      This parameter has a shape this form cannot render yet. Leave it to its default, or submit the
      job through the API.
    </span>
  {/if}

  {#if schema.description}
    <span class="text-xs text-muted-foreground">{schema.description}</span>
  {/if}
</label>
