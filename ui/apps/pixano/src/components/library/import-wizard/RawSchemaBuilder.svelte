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
    validateRawSchemaFields,
    type RawFields,
  } from "./rawSchema";
  import { WIZARD_DISCLOSURE_CLASS, WIZARD_DISCLOSURE_SUMMARY_CLASS } from "./wizardStyles";

  interface Props {
    raw: RawFields;
  }

  let { raw = $bindable() }: Props = $props();
  const validationError = $derived(validateRawSchemaFields(raw));
</script>

<div class="space-y-6">
  <AnnotationSlotsPicker
    choices={ANNOTATION_CHOICES[raw.task]}
    locked={LOCKED_ANNOTATIONS[raw.task]}
    bind:selected={raw.annotations}
  />

  <fieldset class="min-w-0 space-y-3">
    <legend class="text-sm font-semibold text-foreground">Object attributes</legend>
    <AttrsEditor
      bind:rows={raw.entityAttrs}
      hint="Per-object fields, e.g. category or occlusion."
    />
  </fieldset>

  <details class={WIZARD_DISCLOSURE_CLASS} open={raw.recordAttrs.length > 0}>
    <summary class={WIZARD_DISCLOSURE_SUMMARY_CLASS}>
      Record attributes (optional)
      {#if raw.recordAttrs.length}<span class="ml-1 text-muted-foreground">
          ({raw.recordAttrs.length})
        </span>{/if}
    </summary>
    <div class="mt-3">
      <AttrsEditor
        bind:rows={raw.recordAttrs}
        hint="Per-record fields, e.g. location or weather. Values can be edited after import."
        allowRequired={false}
      />
    </div>
  </details>

  {#if validationError}
    <p class="text-sm text-destructive" role="alert">{validationError}</p>
  {/if}
</div>
