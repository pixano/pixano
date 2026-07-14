<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import AnnotationSlotsPicker from "./AnnotationSlotsPicker.svelte";
  import AttrsEditor from "./AttrsEditor.svelte";
  import {
    ANNOTATION_CHOICES,
    LOCKED_ANNOTATIONS,
    validateRawFields,
    type RawFields,
  } from "./rawSchema";

  interface Props {
    raw: RawFields;
  }

  let { raw = $bindable() }: Props = $props();

  const validationError = $derived(validateRawFields(raw));

  const labelClass = "text-xs font-semibold uppercase tracking-widest text-muted-foreground";
  const inputClass =
    "w-full rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground " +
    "placeholder:text-muted-foreground/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
  const segmentClass = (active: boolean) =>
    `rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
      active
        ? "border-primary bg-primary/10 text-primary"
        : "border-border text-muted-foreground hover:border-primary/40"
    }`;
</script>

<div class="space-y-4 rounded-xl border border-border p-4">
  {#if raw.task === "video"}
    <div class="space-y-1.5">
      <p class={labelClass}>Video handling</p>
      <div class="flex gap-1.5">
        <button
          type="button"
          class={segmentClass(raw.framesMode === "extract")}
          onclick={() => (raw.framesMode = "extract")}
        >
          Extract frames (annotate)
        </button>
        <button
          type="button"
          class={segmentClass(raw.framesMode === "reference")}
          onclick={() => (raw.framesMode = "reference")}
        >
          Reference clips (metadata only)
        </button>
      </div>
      {#if raw.framesMode === "extract"}
        <div class="flex items-center gap-2">
          <input
            type="number"
            min="1"
            class="{inputClass} w-32"
            placeholder="All frames"
            bind:value={raw.maxFrames}
            aria-label="Max frames per video"
          />
          <p class="text-xs text-muted-foreground">
            Max frames per video (uniform stride) — long videos can extract a lot of frames.
          </p>
        </div>
      {:else}
        <p class="text-xs text-muted-foreground">
          Clips import as references (metadata + file). In-app playback is not available in this
          release — choose Extract frames to annotate or browse them.
        </p>
      {/if}
    </div>
  {/if}

  <div class="space-y-1.5">
    <p class={labelClass}>Record attributes</p>
    <AttrsEditor
      bind:rows={raw.recordAttrs}
      hint="One value per item (e.g. weather: str, captured_at: str). Values are filled in Pixano after import."
      allowRequired={false}
    />
  </div>

  <div class="space-y-1.5">
    <p class={labelClass}>Object attributes</p>
    <AttrsEditor
      bind:rows={raw.entityAttrs}
      hint="Attributes each annotated object carries (e.g. category: str)."
    />
  </div>

  <div class="space-y-1.5">
    <p class={labelClass}>Annotations</p>
    <AnnotationSlotsPicker
      choices={ANNOTATION_CHOICES[raw.task]}
      locked={LOCKED_ANNOTATIONS[raw.task]}
      bind:selected={raw.annotations}
    />
  </div>

  {#if validationError}
    <p class="text-xs text-destructive">{validationError}</p>
  {/if}
</div>
