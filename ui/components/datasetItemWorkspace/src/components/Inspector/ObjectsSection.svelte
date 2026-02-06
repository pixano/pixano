<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Eye, EyeOff, SlidersHorizontal } from "lucide-svelte";
  import { createEventDispatcher, onMount } from "svelte";
  import { derived } from "svelte/store";

  import { IconButton, Source } from "@pixano/core/src";

  import { toggleObjectDisplayControl } from "../../lib/api/objectsApi";
  import { GROUND_TRUTH, OTHER } from "../../lib/constants";
  import { annotations } from "../../lib/stores/datasetItemWorkspaceStores";
  import OptionsAndFilters from "./OptionsAndFilters.svelte";

  const dispatch = createEventDispatcher();

  export let source: Source | undefined;
  export let countText: string;
  let modelName: string = OTHER;
  let sectionTitle: string = OTHER + " - unknown";
  let showFilters = false;

  let visibilityStatus = derived([annotations], ([$annotations]) =>
    //Note: as we removed grouping by model, we don't filter by source anymore
    //$annotations.filter((ann) => isAnnFromSource(ann)).every((ann) => ann.ui.displayControl.hidden)
    $annotations.every((ann) => ann.ui.displayControl.hidden) ? "hidden" : "shown",
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

<section class="flex flex-col">
  <div class="flex items-center justify-between text-foreground gap-2 w-full px-1 py-2 sticky top-0 bg-card z-10 border-b border-border/30">
    <IconButton {tooltipContent} on:click={handleVisibilityIconClick}>
      {#if $visibilityStatus === "hidden"}
        <EyeOff class="h-4" />
      {:else}
        <Eye class="h-4" />
      {/if}
    </IconButton>
    <h3 class="text-xs font-semibold uppercase tracking-wider text-muted-foreground grow">{sectionTitle}</h3>
    <IconButton
      tooltipContent={"Generic options"}
      selected={showFilters}
      on:click={() => (showFilters = !showFilters)}
    >
      <SlidersHorizontal />
    </IconButton>
    <slot name="modelSelection" />
    <span
      class="text-xs text-muted-foreground tabular-nums bg-muted rounded-full px-2 py-0.5"
      title="object count - (filtered / total) if some objects are filtered out)"
    >
      {countText}
    </span>
  </div>
  <div style:display={showFilters ? "block" : "none"}>
    <OptionsAndFilters
      on:filter={(event) => dispatch("filter", event.detail)}
      on:confidenceThresholdChange={() => dispatch("confidenceThresholdChange")}
    />
  </div>
  <div class="flex flex-col gap-1.5 px-1 pt-1 pb-2">
    <slot />
  </div>
</section>
