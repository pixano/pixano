<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Eye, EyeOff } from "lucide-svelte";

  import { IconButton, Source } from "@pixano/core/src";

  import { toggleObjectDisplayControl } from "../../lib/api/objectsApi";
  import { OTHER } from "../../lib/constants";
  import { annotations } from "../../lib/stores/datasetItemWorkspaceStores";
  import { onMount } from "svelte";
  import { derived } from "svelte/store";

  export let source: Source | undefined;
  export let numberOfItem: number;
  let modelName: string = OTHER;
  let sectionTitle: string = OTHER + " - unknown";
  let visibilityStatus = derived([annotations], ([$annotations]) =>
    $annotations
      .filter((ann) => ann.data.source_ref.id === source?.id)
      .every((ann) => ann.ui.displayControl?.hidden)
      ? "hidden"
      : "shown",
  );

  onMount(() => {
    if (source && !["human", "ground_truth"].includes(source.data.kind.toLowerCase())) {
      modelName = source.data.name;
      sectionTitle = source.data.kind + " - " + source.data.name;
    }
  });

  $: tooltipContent =
    $visibilityStatus === "hidden" ? `Show ${modelName} objects` : `Hide ${modelName} objects`;

  const handleVisibilityIconClick = () => {
    const isHidden = $visibilityStatus === "hidden";
    annotations.update((anns) =>
      anns.map((ann) => {
        return ann.data.source_ref.id === source?.id
          ? toggleObjectDisplayControl(ann, "hidden", !isHidden)
          : ann;
      }),
    );
  };
</script>

<section class="h-full pb-10">
  <div class="flex items-center justify-between text-slate-800">
    <div class="flex items-center gap-3 w-full">
      <IconButton {tooltipContent} on:click={handleVisibilityIconClick}>
        {#if $visibilityStatus === "hidden"}
          <EyeOff class="h-4" />
        {:else}
          <Eye class="h-4" />
        {/if}
      </IconButton>
      <h3 class="uppercase font-medium grow">{sectionTitle}</h3>
      <slot name="modelSelection" />
      <p>{numberOfItem}</p>
    </div>
  </div>
  <div class="p-2 pt-0 max-h-full overflow-y-auto">
    <slot />
  </div>
</section>
