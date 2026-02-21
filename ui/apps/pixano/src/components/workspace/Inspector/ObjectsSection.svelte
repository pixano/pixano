<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { Snippet } from "svelte";

  import { Eye, EyeOff, SlidersHorizontal } from "lucide-svelte";

  import { IconButton, Source, type Entity } from "$lib/ui";

  import { toggleAnnotationDisplayControl } from "$lib/utils/displayControl";
  import { GROUND_TRUTH, OTHER } from "$lib/constants/workspaceConstants";
  import { annotations } from "$lib/stores/workspaceStores.svelte";
  import OptionsAndFilters from "./OptionsAndFilters.svelte";

  interface Props {
    source?: Source;
    countText: string;
    onFilter?: (entities: Entity[]) => void;
    onConfidenceThresholdChange?: () => void;
    children?: Snippet;
    modelSelection?: Snippet;
  }

  let {
    source = undefined,
    countText,
    onFilter,
    onConfidenceThresholdChange,
    children,
    modelSelection,
  }: Props = $props();

  const modelName = $derived(source?.data.name ?? OTHER);
  const sectionTitle = $derived.by(() => {
    if (source) {
      return source.data.kind === "ground_truth"
        ? GROUND_TRUTH
        : source.data.kind + " - " + source.data.name;
    }
    return `${OTHER} - unknown`;
  });
  let showFilters = $state(false);

  const visibilityStatus = $derived(
    annotations.value.every((ann) => ann.ui.displayControl.hidden) ? "hidden" : "shown",
  );

  const tooltipContent = $derived(
    visibilityStatus === "hidden" ? `Show ${modelName} objects` : `Hide ${modelName} objects`,
  );

  const handleVisibilityIconClick = () => {
    const isHidden = visibilityStatus === "hidden";
    annotations.update((anns) =>
      anns.map((ann) => {
        //return isAnnFromSource(ann) ? toggleObjectDisplayControl(ann, "hidden", !isHidden) : ann;
        //TMP(?) now that there is only a global source group, we change vis for all
        return toggleAnnotationDisplayControl(ann, "hidden", !isHidden);
      }),
    );
  };
</script>

<section class="flex flex-col">
  <div
    class="flex items-center justify-between text-foreground gap-2 w-full px-1 py-2 sticky top-0 bg-card z-10 border-b border-border/30"
  >
    <IconButton {tooltipContent} onclick={handleVisibilityIconClick}>
      {#if visibilityStatus === "hidden"}
        <EyeOff class="h-4" />
      {:else}
        <Eye class="h-4" />
      {/if}
    </IconButton>
    <h3 class="text-xs font-semibold uppercase tracking-wider text-muted-foreground grow">
      {sectionTitle}
    </h3>
    <IconButton
      tooltipContent={"Generic options"}
      selected={showFilters}
      onclick={() => (showFilters = !showFilters)}
    >
      <SlidersHorizontal />
    </IconButton>
    {@render modelSelection?.()}
    <span
      class="text-xs text-muted-foreground tabular-nums bg-muted rounded-full px-2 py-0.5"
      title="object count - (filtered / total) if some objects are filtered out)"
    >
      {countText}
    </span>
  </div>
  <div style:display={showFilters ? "block" : "none"}>
    <OptionsAndFilters
      onFilter={onFilter}
      onConfidenceThresholdChange={onConfidenceThresholdChange}
    />
  </div>
  <div class="flex flex-col gap-1.5 px-1 pt-1 pb-2">
    {@render children?.()}
  </div>
</section>
