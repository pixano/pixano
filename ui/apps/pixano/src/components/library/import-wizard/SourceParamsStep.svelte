<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { CaretDown, CaretRight, FolderOpen } from "phosphor-svelte";

  import { parseAdvancedSpec, showsLerobotFields, type WizardFields } from "./wizardUtils";

  interface Props {
    fields: WizardFields;
    advancedJson: string;
  }

  let { fields = $bindable(), advancedJson = $bindable() }: Props = $props();

  let showAdvanced = $state(false);
  const advancedError = $derived(parseAdvancedSpec(advancedJson).error);
  const showLerobot = $derived(showsLerobotFields(fields));

  const labelClass = "text-xs font-semibold uppercase tracking-widest text-muted-foreground";
  const inputClass =
    "w-full rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground " +
    "placeholder:text-muted-foreground/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
</script>

<div class="px-6 sm:px-7 pb-2 space-y-4">
  <div class="space-y-1.5">
    <label class={labelClass} for="wizard-source">Source</label>
    <div class="relative">
      <FolderOpen
        weight="regular"
        class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
      />
      <input
        id="wizard-source"
        type="text"
        class="{inputClass} pl-9"
        placeholder="/path/on/server or org/name (Hugging Face)"
        bind:value={fields.source}
      />
    </div>
    <p class="text-xs text-muted-foreground">
      A folder path on the server, or a Hugging Face dataset id for LeRobot sources.
    </p>
  </div>

  <div class="grid gap-4 sm:grid-cols-2">
    <div class="space-y-1.5">
      <label class={labelClass} for="wizard-name">Dataset name (optional)</label>
      <input
        id="wizard-name"
        type="text"
        class={inputClass}
        placeholder="Defaults to the source name"
        bind:value={fields.name}
      />
    </div>
    <div class="space-y-1.5">
      <label class={labelClass} for="wizard-mode">If the dataset exists</label>
      <select id="wizard-mode" class={inputClass} bind:value={fields.mode}>
        <option value="create">Fail (create only)</option>
        <option value="overwrite">Overwrite it</option>
      </select>
    </div>
  </div>

  <div class="space-y-1.5">
    <label class={labelClass} for="wizard-media">Media storage</label>
    <select id="wizard-media" class={inputClass} bind:value={fields.media}>
      <option value="embed">Embed in the dataset (self-contained, default)</option>
      <option value="uri">Keep URIs (media served by your storage)</option>
    </select>
  </div>

  {#if showLerobot}
    <div class="grid gap-4 sm:grid-cols-2">
      <div class="space-y-1.5">
        <label class={labelClass} for="wizard-episodes">Episodes (optional)</label>
        <input
          id="wizard-episodes"
          type="text"
          class={inputClass}
          placeholder="e.g. 0:4 or 1,3,7"
          bind:value={fields.episodes}
        />
      </div>
      <div class="space-y-1.5">
        <label class={labelClass} for="wizard-max-frames">Max frames / episode (optional)</label>
        <input
          id="wizard-max-frames"
          type="number"
          min="1"
          class={inputClass}
          placeholder="All frames"
          bind:value={fields.maxFrames}
        />
      </div>
    </div>
  {/if}

  <div class="rounded-xl border border-border">
    <button
      type="button"
      class="flex w-full items-center gap-2 px-4 py-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground hover:text-foreground"
      onclick={() => (showAdvanced = !showAdvanced)}
    >
      {#if showAdvanced}
        <CaretDown weight="bold" class="h-3.5 w-3.5" />
      {:else}
        <CaretRight weight="bold" class="h-3.5 w-3.5" />
      {/if}
      Advanced spec (JSON)
    </button>
    {#if showAdvanced}
      <div class="space-y-2 border-t border-border p-4">
        <p class="text-xs text-muted-foreground">
          Optional overrides merged over the fields above — the same keys as
          <span class="font-mono">dataset.yaml</span>
          (dataset, schema with any attributes, ids, options).
        </p>
        <textarea
          class="h-36 w-full resize-y rounded-lg border border-border bg-card p-3 font-mono text-xs text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          placeholder={'{\n  "schema": {"record": {"attrs": {"weather": "str"}}}\n}'}
          bind:value={advancedJson}
        ></textarea>
        {#if advancedError}
          <p class="text-xs text-destructive">{advancedError}</p>
        {/if}
      </div>
    {/if}
  </div>
</div>
