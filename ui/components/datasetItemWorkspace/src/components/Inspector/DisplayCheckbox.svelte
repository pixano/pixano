<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { BaseSchema, Checkbox, type DisplayControl } from "@pixano/core";

  export let isAnnotationEmpty: boolean;
  export let handleSetAnnotationDisplayControl: (
    displayControlProperty: keyof DisplayControl,
    isVisible: boolean,
    base_schema: BaseSchema | null,
  ) => void;

  export let annotationIsVisible: boolean;
  export let annotationName: string;
</script>

{#if !isAnnotationEmpty}
  <div class="flex gap-2 mt-2 items-center">
    <p class="font-light first-letter:uppercase">{annotationName}</p>
    <Checkbox
      handleClick={() =>
        handleSetAnnotationDisplayControl("hidden", annotationIsVisible, BaseSchema.BBox)}
      bind:checked={annotationIsVisible}
      title={annotationIsVisible ? "Hide" : "Show"}
      class="mx-1"
    />
  </div>
{/if}
