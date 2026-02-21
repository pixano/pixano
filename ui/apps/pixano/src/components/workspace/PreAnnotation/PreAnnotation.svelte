<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  
  // Imports
  import { BoxSelectIcon, Check, Filter } from "lucide-svelte";
  import { untrack } from "svelte";

  import { Switch, Tooltip } from "bits-ui";

  import { Slider } from "bits-ui";

  import { Annotation, cn, IconButton, PrimaryButton } from "$lib/ui";

  import { getAnnotationsToPreAnnotate, sortAndFilterAnnotations } from "$lib/utils/entityLookupUtils";
  import { mapAnnotationWithNewStatus } from "$lib/utils/annotationMapping";
  import {
    annotations,
    colorScale,
    preAnnotationIsActive,
  } from "$lib/stores/workspaceStores.svelte";
  import { currentFrameIndex } from "$lib/stores/videoStores.svelte";
  import type { EntityProperties } from "$lib/types/workspace";
  import CreateFeatureInputs from "../Features/CreateFeatureInputs.svelte";

  let isFormValid: boolean = $state(false);
  let confidenceFilterValue = $state([0]);
  let objectProperties: EntityProperties = $state({});

  const annotationsToReview = $derived(getAnnotationsToPreAnnotate(annotations.value));
  const filteredAnnotationsToReview = $derived(
    sortAndFilterAnnotations(annotationsToReview, confidenceFilterValue, currentFrameIndex.value),
  );
  let annotationToReview = $derived(filteredAnnotationsToReview[0]);
  let color: string = $derived(colorScale.value[1](annotationToReview?.id || ""));

  $effect(() => {
    const isActive = preAnnotationIsActive.value;
    const count = annotationsToReview.length;
    if (isActive && count === 0) {
      untrack(() => {
        preAnnotationIsActive.value = false;
        annotations.update((objects) =>
          objects.map((object) => {
            object.ui.displayControl.highlighted = "all";
            return object;
          }),
        );
      });
    }
  });

  const onAcceptItem = () => {
    annotationToReview.ui.review_state = "accepted";
    annotationToReview.ui.displayControl.highlighted = "none";

    annotations.update((objects) => [
      ...mapAnnotationWithNewStatus(objects, filteredAnnotationsToReview, "accepted", objectProperties),
      annotationToReview,
    ]);
  };

  const onRejectItem = () => {
    annotations.update((objects) =>
      mapAnnotationWithNewStatus(objects, filteredAnnotationsToReview, "rejected"),
    );
  };

  const onSwitchChange = (checked: boolean | undefined) => {
    preAnnotationIsActive.value = checked || false;
    annotations.update((objects) => {
      const objectsToPreAnnotate = getAnnotationsToPreAnnotate(objects);
      const tempObjects = sortAndFilterAnnotations(
        objectsToPreAnnotate,
        confidenceFilterValue,
        currentFrameIndex.value,
      );
      return objects.map((object) => {
        object.ui.displayControl.highlighted = preAnnotationIsActive.value ? "none" : "all";
        if (object.id === tempObjects[0]?.id && preAnnotationIsActive.value) {
          object.ui.displayControl.highlighted = "self";
        }
        return object;
      });
    });
  };

  const onSliderChange = (value: number[] | undefined) => {
    confidenceFilterValue = value || [0];
    if (annotationsToReview.length === 0) {
      preAnnotationIsActive.value = false;
    }
  };
</script>

{#if annotationsToReview.length > 0}
  <div class="flex justify-between my-4">
    <div class="flex gap-4">
      <Tooltip.Root>
        <Tooltip.Trigger>
          <Switch.Root
            onCheckedChange={onSwitchChange}
            class={cn(
              "peer inline-flex h-[24px] w-[44px] shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors data-[state=checked]:bg-primary data-[state=unchecked]:bg-input",
              { "pointer-events-none": !annotationsToReview.length },
            )}
          >
            <Switch.Thumb
              class="pointer-events-none block h-5 w-5 rounded-full bg-background shadow-lg ring-0 transition-transform data-[state=checked]:translate-x-5 data-[state=unchecked]:translate-x-0"
            />
          </Switch.Root>
        </Tooltip.Trigger>
        {#if annotationsToReview.length === 0}
          <Tooltip.Content
            class="z-50 overflow-hidden rounded-md border border-border/40 bg-popover/90 backdrop-blur-sm px-3 py-1.5 text-sm text-popover-foreground shadow-glass-sm"
          >
            <p>No annotations to review</p>
          </Tooltip.Content>
        {/if}
      </Tooltip.Root>
      <h3 class="uppercase font-medium">PRE ANNOTATION</h3>
    </div>
    {#if preAnnotationIsActive.value}
      <span>{filteredAnnotationsToReview.length}</span>
    {/if}
  </div>
  {#if preAnnotationIsActive.value}
    <div class="my-2 flex items-center">
      <IconButton tooltipContent="confidence slider">
        <Filter />
      </IconButton>
      <div class="px-8 w-full">
        <div class="flex gap-4 w-full">
          <span>0</span>
          <Slider.Root
            type="multiple"
            bind:value={confidenceFilterValue}
            max={1}
            step={0.01}
            onValueChange={onSliderChange}
            class="relative flex w-full touch-none select-none items-center"
          >
            <span class="relative h-2 w-full grow overflow-hidden rounded-full bg-card">
              <Slider.Range class="absolute h-full bg-primary" />
            </span>
            <Slider.Thumb
              index={0}
              class="block h-5 w-5 rounded-full border-2 border-primary bg-background ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50"
            />
          </Slider.Root>
          <span>1</span>
        </div>
      </div>
    </div>
    {#if annotationToReview}
      <div class="bg-card rounded-sm p-4 pb-0 mt-4 relative max-h-[60vh] overflow-y-auto">
        <p class="flex gap-2">
          <BoxSelectIcon {color} />
          <span>{annotationToReview.id}</span>
        </p>
        <div class="flex flex-col gap-4 py-4">
          {#key annotationToReview.id}
            <CreateFeatureInputs
              bind:isFormValid
              bind:objectProperties
              isAutofocusEnabled={false}
              baseSchema={annotationToReview.table_info.base_schema}
            />
            <!-- initialValues={annotationToReview.features}  // need rework/rethink -->
          {/key}
        </div>
        <div class="flex gap-4 mt-4 justify-center sticky bottom-0 pb-2 left-[50%] bg-card">
          <PrimaryButton onclick={onAcceptItem} isSelected disabled={!isFormValid}>
            <Check />Accept
          </PrimaryButton>
          <PrimaryButton onclick={onRejectItem}>Reject</PrimaryButton>
        </div>
      </div>
    {/if}
  {/if}
{/if}
