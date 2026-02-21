<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  /* eslint-disable svelte/no-at-html-tags */
  // Imports
  import { Button } from "bits-ui";

  import {
    Annotation,
    BaseSchema,
    Mask,
    ShapeType,
    Tracklet,
    WorkspaceType,
    type SaveRectangleShape,
    type SaveTrackletShape,
  } from "$lib/ui";
  import { cn } from "$lib/utils/styleUtils";
  import { buttonVariants } from "$lib/utils/buttonVariants";
  import { pixanoInferenceToValidateTrackingMasks } from "$lib/stores/inferenceStores.svelte";

  import { datasetSchema } from "$lib/stores/appStores.svelte";
  import { getBoundingBoxFromMaskSvgPaths } from "$lib/utils/maskUtils";
  import { addNewInput, mapShapeInputsToFeatures } from "$lib/utils/featureMapping";
  import { saveTo } from "$lib/utils/saveItemUtils";
  import { sortByFrameIndex } from "$lib/utils/videoUtils";
  import {
    defineCreatedAnnotation,
    findOrCreateSubAndTopEntities,
    getFrameIndexFromViewRef,
  } from "$lib/utils/entityOperations";
  import { mapShapeType2BaseSchema, temporayTextSpanId } from "$lib/constants/workspaceConstants";
  import {
    annotations,
    entities,
    itemMetas,
    newShape,
  } from "$lib/stores/workspaceStores.svelte";
  import { currentFrameIndex } from "$lib/stores/videoStores.svelte";
  import type {
    CreateEntityInputs,
    EntityProperties,
  } from "$lib/types/workspace";
  import CreateFeatureInputs from "../Features/CreateFeatureInputs.svelte";
  import RelinkAnnotation from "./RelinkAnnotation.svelte";

  interface Props {
    currentTab: "scene" | "objects";
  }

  let { currentTab = $bindable() }: Props = $props();
  let isFormValid: boolean = $state(false);
  let formInputs: CreateEntityInputs = $state([]);

  let objectProperties: EntityProperties = $state({});
  let selectedEntityId: string = $state("");

  const handleFormSubmit = () => {
    removeTemporaryTextSpan();
    currentTab = "objects";

    if (newShape.value.status !== "saving") {
      return;
    }

    let newAnnotation: Annotation | undefined = undefined;
    let newTracklet: Annotation | undefined = undefined;

    const isVideo = itemMetas.value?.type === WorkspaceType.VIDEO;
    const isFromTracking = isVideo && pixanoInferenceToValidateTrackingMasks.value.length > 1;

    const features = mapShapeInputsToFeatures(objectProperties, formInputs);

    const { topEntity, subEntity } = findOrCreateSubAndTopEntities(
      selectedEntityId,
      newShape.value,
      features,
    );

    newAnnotation = defineCreatedAnnotation(
      subEntity ?? topEntity,
      features,
      newShape.value,
      newShape.value.viewRef,
      datasetSchema.value,
      isVideo,
      currentFrameIndex.value,
    );

    if (!newAnnotation) return;

    newAnnotation.ui.displayControl = { hidden: false, editing: false, highlighted: "self" };
    newAnnotation.ui.top_entities = subEntity ? [topEntity, subEntity] : [topEntity];
    topEntity.ui.childs?.push(newAnnotation);

    if (subEntity) subEntity.ui.childs?.push(newAnnotation);

    let tracking_masks: Mask[] = [];
    const addedAnnotations: Annotation[] = [newAnnotation];

    if (newShape.value.type === ShapeType.mask || newShape.value.type === ShapeType.polygon) {
      const bboxCoords = getBoundingBoxFromMaskSvgPaths(newShape.value.masksImageSVG);
      if (bboxCoords) {
        const bboxShape: SaveRectangleShape = {
          ...(newShape.value as unknown as SaveRectangleShape),
          type: ShapeType.bbox,
          attrs: bboxCoords,
        };
        const newBBox = defineCreatedAnnotation(
          subEntity ?? topEntity,
          features,
          bboxShape,
          newShape.value.viewRef,
          datasetSchema.value,
          isVideo,
          currentFrameIndex.value,
        );
        if (newBBox) {
          newBBox.ui.displayControl = { hidden: false, editing: false, highlighted: "none" };
          newBBox.ui.top_entities = subEntity ? [topEntity, subEntity] : [topEntity];
          topEntity.ui.childs?.push(newBBox);
          if (subEntity) subEntity.ui.childs?.push(newBBox);
          saveTo("add", newBBox);
          addedAnnotations.push(newBBox);
        }
      }
    }

    if (isVideo) {
      let lastFrameIndex = currentFrameIndex.value;
      if (isFromTracking) {
        for (const tr_mask of pixanoInferenceToValidateTrackingMasks.value.slice(1)) {
          // really create Mask instance (before it's just a cast)
          tracking_masks.push(new Mask({ ...tr_mask }));
        }
        for (const tr_mask of tracking_masks) {
          //fill some missing info in tracking masks
          tr_mask.data.entity_ref = newAnnotation.data.entity_ref;
          tr_mask.table_info = newAnnotation.table_info;
          const tr_frame_idx = getFrameIndexFromViewRef(tr_mask.data.view_ref);
          tr_mask.ui = { ...newAnnotation.ui, frame_index: tr_frame_idx };
          topEntity.ui.childs?.push(tr_mask);
          if (subEntity) subEntity.ui.childs?.push(tr_mask);
          //get lastFrameIndex from tracking masks
          lastFrameIndex = Math.max(tr_frame_idx, lastFrameIndex);
        }
      }
      // for video, there is 1 anns, 1 track (may have 1 sub entity), 1 tracklet
      // -> add tracklet
      const candidate_tracklets = topEntity.ui.childs?.filter(
        (ann) =>
          ann.is_type(BaseSchema.Tracklet) &&
          ann.data.view_ref.name === newShape.value.viewRef.name &&
          (ann as Tracklet).data.start_timestep <= currentFrameIndex.value &&
          (ann as Tracklet).data.end_timestep >= lastFrameIndex,
      );
      if (candidate_tracklets && candidate_tracklets.length === 1) {
        const candidate_tracklet = candidate_tracklets[0] as Tracklet;
        //NOTE: we add the new object "as it is" in the candidate tracklet
        //it means that the tracklet may be wider than the new shape "range" (1 frame at creation)
        //-- this is potentially dangerous... but *should* be fine --
        candidate_tracklet.ui.childs.push(newAnnotation);
        if (isFromTracking) {
          for (const tr_mask of tracking_masks) candidate_tracklet.ui.childs.push(tr_mask);
        }
        candidate_tracklet.ui.childs.sort(sortByFrameIndex);
      } else {
        const trackletShape: SaveTrackletShape = {
          type: ShapeType.tracklet,
          status: newShape.value.status,
          itemId: "", //unused from SaveShapeBase
          imageWidth: 0, //unused from SaveShapeBase
          imageHeight: 0, //unused from SaveShapeBase
          viewRef: { id: "", name: newShape.value.viewRef.name },
          attrs: {
            start_timestep: currentFrameIndex.value,
            end_timestep: lastFrameIndex,
            //TODO timestamp management...
            start_timestamp: currentFrameIndex.value,
            end_timestamp: lastFrameIndex,
          },
        };
        newTracklet = defineCreatedAnnotation(
          topEntity,
          features,
          trackletShape,
          trackletShape.viewRef,
          datasetSchema.value,
          isVideo,
          currentFrameIndex.value,
        );
        if (!newTracklet) return;
        newTracklet.ui.displayControl = { hidden: false, editing: false, highlighted: "all" };
        (newTracklet as Tracklet).ui.childs = [newAnnotation];
        if (isFromTracking) {
          for (const tr_mask of tracking_masks) (newTracklet as Tracklet).ui.childs.push(tr_mask);
        }

        saveTo("add", newTracklet);
        //TODO Note: we may have to manage "spatial object" entity too...
        topEntity.ui.childs?.push(newTracklet);
      }
    }

    if (!entities.value.includes(topEntity)) {
      saveTo("add", topEntity);
    }

    if (subEntity && !entities.value.includes(subEntity)) {
      saveTo("add", subEntity);
    }

    saveTo("add", newAnnotation);

    if (isFromTracking) {
      for (const tr_mask of tracking_masks) {
        saveTo("add", tr_mask);
      }
    }

    // push new entity & sub(s)
    entities.update((ents) => {
      if (topEntity && !ents.includes(topEntity)) ents.push(topEntity);
      if (subEntity && !ents.includes(subEntity)) ents.push(subEntity);
      return ents;
    });

    //push new annotations
    annotations.update((oldObjects) => {
      const objectsWithoutHighlighted: Annotation[] = oldObjects.map((object) => {
        object.ui.displayControl.highlighted = "none";
        object.ui.displayControl = { ...object.ui.displayControl, editing: false };
        return object;
      });
      return [
        ...objectsWithoutHighlighted,
        ...addedAnnotations,
        ...(isFromTracking ? tracking_masks : []),
        ...(newTracklet ? [newTracklet] : []),
      ];
    });

    annotations.value.sort((a, b) => sortByFrameIndex(a, b));
    for (const tname in objectProperties) {
      for (const feat in objectProperties[tname]) {
        if (typeof objectProperties[feat] === "string") {
          addNewInput(itemMetas.value?.featuresList, "objects", feat, objectProperties[feat]);
        }
      }
    }

    newShape.value = { status: "none", shouldReset: true };
  };

  function removeTemporaryTextSpan() {
    if (annotations.value.find((ann) => ann.id === temporayTextSpanId)) {
      annotations.update((anns) => anns.filter((ann) => ann.id !== temporayTextSpanId));
    }
  }
  function handleCancel() {
    newShape.value = { status: "none", shouldReset: true };
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (event.key === "Escape") {
      handleCancel();
    }
  }

  function handleSubmit(event: SubmitEvent) {
    event.preventDefault();
    handleFormSubmit();
  }

  //set specific header text for different kind of shape
  let saveText = $derived.by(() => {
    if (newShape.value.status !== "saving") return "Save";
    let text = "Save " + newShape.value.type;
    if (newShape.value.type === ShapeType.textSpan) {
      text += " <i>" + newShape.value.attrs.mention + "</i>";
    }
    return text;
  });

  $effect(() => {
    return () => removeTemporaryTextSpan();
  });
</script>

{#if newShape.value.status === "saving"}
  <form class="flex flex-col gap-4 p-4" onsubmit={handleSubmit}>
    <p>{@html saveText}</p>
    <RelinkAnnotation
      bind:selectedEntityId
      baseSchema={mapShapeType2BaseSchema[newShape.value.type]}
      viewRef={newShape.value.viewRef}
    />
    <div class="max-h-[calc(100vh-250px)] overflow-y-auto flex flex-col gap-4">
      <CreateFeatureInputs
        bind:isFormValid
        bind:formInputs
        bind:objectProperties
        {selectedEntityId}
        baseSchema={mapShapeType2BaseSchema[newShape.value.type]}
      />
    </div>
    <div class="flex gap-4">
      <Button.Root type="button" class={cn(buttonVariants(), "text-primary-foreground")} onclick={handleCancel}>Cancel</Button.Root>
      <Button.Root type="submit" class={cn(buttonVariants(), "text-primary-foreground")} disabled={!isFormValid}>Confirm</Button.Root>
    </div>
  </form>
{/if}
<svelte:window onkeydown={handleKeyDown} />
