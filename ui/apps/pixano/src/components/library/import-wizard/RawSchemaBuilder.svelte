<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import AnnotationSlotsPicker from "./AnnotationSlotsPicker.svelte";
  import EntityAttrsEditor from "./EntityAttrsEditor.svelte";
  import {
    ANNOTATION_CHOICES,
    DEFAULT_ANNOTATIONS,
    validateRawFields,
    type RawFields,
    type RawMediaKind,
  } from "./rawSchema";

  interface Props {
    raw: RawFields;
  }

  let { raw = $bindable() }: Props = $props();

  const KINDS: { kind: RawMediaKind; label: string }[] = [
    { kind: "images", label: "Images" },
    { kind: "videos", label: "Videos" },
    { kind: "texts", label: "Text" },
  ];

  const validationError = $derived(validateRawFields(raw));

  function setKind(kind: RawMediaKind) {
    raw.kind = kind;
    raw.annotations = [...DEFAULT_ANNOTATIONS[kind]];
  }

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
  <div class="space-y-1.5">
    <p class={labelClass}>Media type</p>
    <div class="flex gap-1.5" role="radiogroup" aria-label="Media type">
      {#each KINDS as entry (entry.kind)}
        <button
          type="button"
          class={segmentClass(raw.kind === entry.kind)}
          role="radio"
          aria-checked={raw.kind === entry.kind}
          onclick={() => setKind(entry.kind)}
        >
          {entry.label}
        </button>
      {/each}
    </div>
  </div>

  {#if raw.kind === "images"}
    <div class="space-y-1.5">
      <p class={labelClass}>Views</p>
      <div class="flex gap-1.5">
        <button
          type="button"
          class={segmentClass(raw.viewsMode === "auto")}
          onclick={() => (raw.viewsMode = "auto")}
        >
          Auto from folders
        </button>
        <button
          type="button"
          class={segmentClass(raw.viewsMode === "named")}
          onclick={() => (raw.viewsMode = "named")}
        >
          Name them
        </button>
      </div>
      {#if raw.viewsMode === "auto"}
        <p class="text-xs text-muted-foreground">
          Subfolders become views (e.g. <span class="font-mono">left/</span>
          ,
          <span class="font-mono">right/</span>
          , matched by file name); a flat folder becomes one view.
        </p>
      {:else}
        <input
          type="text"
          class="{inputClass} font-mono"
          placeholder="left, right"
          bind:value={raw.viewNames}
          aria-label="View names"
        />
        <p class="text-xs text-muted-foreground">
          Comma-separated snake_case names; each needs a matching folder in the source.
        </p>
      {/if}
    </div>
  {/if}

  {#if raw.kind === "videos"}
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
          Reference clips (browse)
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
          Clips play in the explorer but cannot be annotated frame by frame in this release.
        </p>
      {/if}
    </div>
  {/if}

  <div class="space-y-1.5">
    <p class={labelClass}>Entity attributes</p>
    <EntityAttrsEditor bind:rows={raw.entityAttrs} />
  </div>

  <div class="space-y-1.5">
    <p class={labelClass}>Annotations</p>
    <AnnotationSlotsPicker choices={ANNOTATION_CHOICES[raw.kind]} bind:selected={raw.annotations} />
  </div>

  {#if validationError}
    <p class="text-xs text-destructive">{validationError}</p>
  {/if}
</div>
