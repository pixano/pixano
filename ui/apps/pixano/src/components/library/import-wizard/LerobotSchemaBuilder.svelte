<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import AnnotationSlotsPicker from "./AnnotationSlotsPicker.svelte";
  import AttrsEditor from "./AttrsEditor.svelte";
  import { validateLerobotFields, type LerobotFields } from "./lerobotSchema";
  import { ANNOTATION_CHOICES, LOCKED_ANNOTATIONS } from "./rawSchema";
  import { WIZARD_DISCLOSURE_CLASS, WIZARD_DISCLOSURE_SUMMARY_CLASS } from "./wizardStyles";

  interface Props {
    schema: LerobotFields;
  }

  let { schema = $bindable() }: Props = $props();
  const validationError = $derived(validateLerobotFields(schema));
</script>

<section aria-label="LeRobot annotation schema" class="space-y-6">
  <AnnotationSlotsPicker
    choices={ANNOTATION_CHOICES.video}
    locked={LOCKED_ANNOTATIONS.video}
    bind:selected={schema.annotations}
  />

  <fieldset class="min-w-0 space-y-3">
    <legend class="text-sm font-semibold text-foreground">Object attributes</legend>
    <AttrsEditor
      bind:rows={schema.entityAttrs}
      hint="Per-object fields, e.g. category or grasp state."
    />
  </fieldset>

  <p class="text-xs leading-relaxed text-muted-foreground">
    Camera views, episode metadata, and robot state/action data are imported automatically.
  </p>
  <details class={WIZARD_DISCLOSURE_CLASS} open={schema.recordAttrs.length > 0}>
    <summary class={WIZARD_DISCLOSURE_SUMMARY_CLASS}>
      Episode attributes (optional)
      {#if schema.recordAttrs.length}<span class="ml-1 text-muted-foreground">
          ({schema.recordAttrs.length})
        </span>{/if}
    </summary>
    <div class="mt-3">
      <AttrsEditor
        bind:rows={schema.recordAttrs}
        hint="Custom episode fields. Values can be edited after import. Episode index, tasks, and length are imported automatically."
        allowRequired={false}
      />
    </div>
  </details>

  {#if validationError}
    <p class="text-sm text-destructive" role="alert">{validationError}</p>
  {/if}
</section>
