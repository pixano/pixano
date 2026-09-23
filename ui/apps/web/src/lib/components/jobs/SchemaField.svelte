<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { asText, fieldKind, toggleChoice, type FieldKind } from "./schemaForm";
  import type { JsonSchema } from "$lib/api/jobs";

  type Props = {
    name: string;
    schema: JsonSchema;
    required: boolean;
    value: unknown;
    /** For a model field: the models the inference serves for its task, if it answered. */
    models?: string[];
    onChange: (value: unknown) => void;
  };

  let { name, schema, required, value, models = [], onChange }: Props = $props();

  const kind: FieldKind = $derived(fieldKind(schema));
  const label = $derived(schema.title ?? name);
</script>

{#if kind === "choices"}
  <!--
    A fieldset, not the label the other fields use: a label activates the first control it
    holds, so clicking "video" ticked "image", and the other boxes had no name of their own.
  -->
  <fieldset class="flex flex-col gap-1 text-sm">
    <legend class="font-medium">
      {label}
      {#if required}<span class="text-destructive" title="Required">*</span>{/if}
    </legend>
    <span class="flex flex-wrap gap-3">
      {#each schema.items?.enum ?? [] as choice (asText(choice))}
        <label class="flex items-center gap-1">
          <input
            type="checkbox"
            class="h-4 w-4"
            checked={Array.isArray(value) && value.includes(choice)}
            onchange={() => onChange(toggleChoice(schema, value, choice))}
          />
          {asText(choice)}
        </label>
      {/each}
    </span>
    {#if schema.description}
      <span class="text-xs text-muted-foreground">{schema.description}</span>
    {/if}
  </fieldset>
{:else}
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
    {:else if kind === "model" && models.length > 0}
      <select
        class="rounded border border-input bg-background px-2 py-1"
        value={asText(value)}
        onchange={(event) => onChange(event.currentTarget.value)}
      >
        {#each models as model (model)}
          <option value={model}>{model}</option>
        {/each}
      </select>
    {:else if kind === "model"}
      <!--
        Typed rather than blocked: the worker asks its own inference, which may not be the one
        this app reaches, and refuses the job with the models it serves if the name is wrong.
      -->
      <input
        type="text"
        class="rounded border border-input bg-background px-2 py-1"
        value={asText(value)}
        onchange={(event) => onChange(event.currentTarget.value)}
      />
      <span class="text-xs text-muted-foreground">
        The inference serves no model for this task that this app can see. Type its name.
      </span>
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
    {:else if kind === "array"}
      <input
        type="text"
        class="rounded border border-input bg-background px-2 py-1"
        placeholder="One value per comma"
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
        This parameter has a shape this form cannot render yet. Leave it to its default, or submit
        the job through the API.
      </span>
    {/if}

    {#if schema.description}
      <span class="text-xs text-muted-foreground">{schema.description}</span>
    {/if}
  </label>
{/if}
