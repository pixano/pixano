<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Eye, EyeOff } from "lucide-svelte";
  import { onMount } from "svelte";
  import { derived } from "svelte/store";

  import { IconButton, Source } from "@pixano/core/src";

  import { toggleObjectDisplayControl } from "../../lib/api/objectsApi";
  import { GROUND_TRUTH, OTHER } from "../../lib/constants";
  import { annotations } from "../../lib/stores/datasetItemWorkspaceStores";

  export let source: Source | undefined;
  export let numberOfItem: number;
  let modelName: string = OTHER;
  let sectionTitle: string = OTHER + " - unknown";

  // const isAnnFromSource = (ann: Annotation): boolean => {
  //   //if we have no source info at all (it shouldn't happens), we have source_ref.id === "";
  //   //note it's different from no corresponding source in source table
  //   return source ? ann.data.source_ref.id === source.id : ann.data.source_ref.id === "";
  // };

  let visibilityStatus = derived([annotations], ([$annotations]) =>
    //Note: as we removed grouping by model, we don't filter by source anymore
    //$annotations.filter((ann) => isAnnFromSource(ann)).every((ann) => ann.ui.displayControl?.hidden)
    $annotations.every((ann) => ann.ui.displayControl?.hidden) ? "hidden" : "shown",
  );

  onMount(() => {
    if (source) {
      modelName = source.data.name;
      if (source.data.kind === "ground_truth") sectionTitle = GROUND_TRUTH;
      else sectionTitle = source.data.kind + " - " + source.data.name;
    }
  });

  $: tooltipContent =
    $visibilityStatus === "hidden" ? `Show ${modelName} objects` : `Hide ${modelName} objects`;

  const handleVisibilityIconClick = () => {
    const isHidden = $visibilityStatus === "hidden";
    annotations.update((anns) =>
      anns.map((ann) => {
        //return isAnnFromSource(ann) ? toggleObjectDisplayControl(ann, "hidden", !isHidden) : ann;
        //TMP(?) now that there is only a global source group, we change vis for all
        return toggleObjectDisplayControl(ann, "hidden", !isHidden);
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
