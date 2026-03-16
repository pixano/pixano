<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  /* eslint-disable svelte/no-at-html-tags */
  // Imports
  import { Button } from "bits-ui";

  import { nanoid } from "nanoid";
  import {
    Annotation,
    BaseSchema,
    BBox,
    Mask,
    SequenceFrame,
    ShapeType,
    Tracklet,
    WorkspaceType,
    type SaveRectangleShape,
    type SaveTrackShape,
  } from "$lib/ui";
  import { cn } from "$lib/utils/styleUtils";
  import { pixanoInferenceToValidateTrackingMasks } from "$lib/stores/inferenceStores.svelte";

  import { rleToBitmapCanvas, getAlphaBoundingBox } from "$lib/utils/maskUtils";
  import { addNewInput, mapShapeInputsToFeatures } from "$lib/utils/featureMapping";
  import { saveTo } from "$lib/utils/saveItemUtils";
  import { sortByFrameIndex } from "$lib/utils/videoUtils";
  import {
    defineCreatedAnnotation,
    findOrCreateEntity,
    getFrameIndex,
  } from "$lib/utils/entityOperations";
  import { mapShapeType2BaseSchema, temporayTextSpanId } from "$lib/constants/workspaceConstants";
  import {
    annotations,
    entities,
    itemMetas,
    newShape,
    views,
  } from "$lib/stores/workspaceStores.svelte";
  import { currentFrameIndex } from "$lib/stores/videoStores.svelte";
  import { trackingSession, cancelTrackingSession } from "$lib/stores/trackingStore.svelte";
  import type {
    CreateEntityInputs,
    EntityProperties,
  } from "$lib/types/workspace";
  import { getWorkspaceContext } from "$lib/workspace/context";
  import CreateFeatureInputs from "../Features/CreateFeatureInputs.svelte";
  import RelinkAnnotation from "./RelinkAnnotation.svelte";

  interface Props {
    currentTab: "scene" | "objects";
  }

  let { currentTab = $bindable() }: Props = $props();
  let isFormValid: boolean = $state(false);
  let formInputs: CreateEntityInputs = $state([]);
  const defaultButtonClass =
    "inline-flex items-center justify-center rounded-lg text-sm font-medium whitespace-nowrap ring-offset-background transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 h-10 px-4 py-2";

  let objectProperties: EntityProperties = $state({});
  let selectedEntityId: string = $state("");
  const { manifest } = getWorkspaceContext();

  const handleFormSubmit = () => {
    removeTemporaryTextSpan();
    currentTab = "objects";

    if (newShape.value.status !== "saving") {
      return;
    }

    let newAnnotation: Annotation | undefined = undefined;
    let newTrack: Annotation | undefined = undefined;
    let newTracks: Annotation[] = [];

    const isVideo = itemMetas.value?.type === WorkspaceType.VIDEO;
    const isFromTracking = isVideo && pixanoInferenceToValidateTrackingMasks.value.length > 1;

    const features = mapShapeInputsToFeatures(objectProperties, formInputs);

    const entity = findOrCreateEntity(
      selectedEntityId,
      newShape.value,
      features,
      manifest,
    );

    newAnnotation = defineCreatedAnnotation(
      entity,
      features,
      newShape.value,
      newShape.value.viewRef,
      manifest,
      isVideo,
      currentFrameIndex.value,
    );

    if (!newAnnotation) return;

    newAnnotation.ui.displayControl = { hidden: false, editing: false, highlighted: "self" };
    newAnnotation.ui.top_entities = [entity];

    // Populate bitmapCanvas on new Mask so it renders immediately after save
    if (newAnnotation.is_type(BaseSchema.Mask)) {
      const maskAnn = newAnnotation as Mask;
      if (Array.isArray(maskAnn.data.counts)) {
        maskAnn.ui.bitmapCanvas = rleToBitmapCanvas(
          maskAnn.data.counts,
          maskAnn.data.size as [number, number],
        );
        maskAnn.ui.bounds = getAlphaBoundingBox(maskAnn.ui.bitmapCanvas) ?? undefined;
      }
    }

    entity.ui.childs?.push(newAnnotation);

    let tracking_masks: Mask[] = [];
    const addedAnnotations: Annotation[] = [newAnnotation];

    if (newShape.value.type === ShapeType.mask) {
      const bboxCoords = newShape.value.maskBounds;
      if (bboxCoords) {
        const bboxShape: SaveRectangleShape = {
          ...(newShape.value as unknown as SaveRectangleShape),
          type: ShapeType.bbox,
          attrs: bboxCoords,
        };
        const newBBox = defineCreatedAnnotation(
          entity,
          features,
          bboxShape,
          newShape.value.viewRef,
          manifest,
          isVideo,
          currentFrameIndex.value,
        );
        if (newBBox) {
          newBBox.ui.displayControl = { hidden: false, editing: false, highlighted: "none" };
          newBBox.ui.top_entities = [entity];
          entity.ui.childs?.push(newBBox);
          saveTo("add", newBBox);
          addedAnnotations.push(newBBox);
        }
      }
    }

    if (isVideo) {
      const tracker = trackingSession.value.tracker;
      const isMultiKeyframe = tracker !== null && tracker.keyframeCount > 1;

      let lastFrameIndex = currentFrameIndex.value;
      if (isFromTracking) {
        for (const tr_mask of pixanoInferenceToValidateTrackingMasks.value.slice(1)) {
          // really create Mask instance (before it's just a cast)
          tracking_masks.push(new Mask({ ...tr_mask }));
        }
        for (const tr_mask of tracking_masks) {
          //fill some missing info in tracking masks
          tr_mask.data.entity_id = newAnnotation.data.entity_id;
          tr_mask.table_info = newAnnotation.table_info;
          const tr_frame_idx = getFrameIndex(tr_mask.data.view_name, tr_mask.data.frame_id);
          tr_mask.ui = { ...newAnnotation.ui, frame_index: tr_frame_idx };
          entity.ui.childs?.push(tr_mask);
          //get lastFrameIndex from tracking masks
          lastFrameIndex = Math.max(tr_frame_idx, lastFrameIndex);
        }
      }
      // Multi-keyframe tracking: create BBox annotations and tracklets per segment
      const trackingKeyframeBBoxes: BBox[] = [];
      if (isMultiKeyframe && newAnnotation.is_type(BaseSchema.BBox)) {
        const segKeyframeArrays = tracker.segmentKeyframes;
        const viewName = tracker.viewName;
        const viewFrames = views.value[viewName];
        let isFirstKfGlobal = true;

        for (const segKfs of segKeyframeArrays) {
          const segBBoxes: BBox[] = [];

          for (const kf of segKfs) {
            const frame = Array.isArray(viewFrames)
              ? (viewFrames[kf.frameIndex] as SequenceFrame | undefined)
              : undefined;
            if (!frame) continue;

            if (isFirstKfGlobal) {
              // Reuse newAnnotation for the very first keyframe of the first segment
              newAnnotation.ui.frame_index = kf.frameIndex;
              newAnnotation.data.frame_index = kf.frameIndex;
              newAnnotation.data.frame_id = frame.id;
              (newAnnotation as BBox).data.coords = [...kf.coords];
              segBBoxes.push(newAnnotation as BBox);
              isFirstKfGlobal = false;
            } else {
              const kfBBox = BBox.cloneForFrame(newAnnotation as BBox, {
                id: nanoid(10),
                coords: [...kf.coords],
                view_name: viewName,
                frame_id: frame.id,
                frame_index: kf.frameIndex,
              });
              kfBBox.ui.displayControl = { hidden: false, editing: false, highlighted: "none" };
              entity.ui.childs?.push(kfBBox);
              trackingKeyframeBBoxes.push(kfBBox);
              addedAnnotations.push(kfBBox);
              segBBoxes.push(kfBBox);
            }
          }

          // Create a Tracklet for this segment
          if (segKfs.length > 0) {
            const segStart = segKfs[0].frameIndex;
            const segEnd = segKfs[segKfs.length - 1].frameIndex;
            lastFrameIndex = Math.max(lastFrameIndex, segEnd);

            const candidate_tracks = entity.ui.childs?.filter(
              (ann) =>
                ann.is_type(BaseSchema.Tracklet) &&
                ann.data.view_name === newShape.value.viewRef.name &&
                (ann as Tracklet).data.start_frame <= segStart &&
                (ann as Tracklet).data.end_frame >= segEnd,
            );
            if (candidate_tracks && candidate_tracks.length === 1) {
              const candidate_track = candidate_tracks[0] as Tracklet;
              for (const bbox of segBBoxes) candidate_track.ui.childs.push(bbox);
              candidate_track.ui.childs.sort(sortByFrameIndex);
            } else {
              const trackShape: SaveTrackShape = {
                type: ShapeType.track,
                status: newShape.value.status,
                itemId: "",
                imageWidth: 0,
                imageHeight: 0,
                viewRef: { id: "", name: newShape.value.viewRef.name },
                attrs: {
                  start_frame: segStart,
                  end_frame: segEnd,
                  start_timestamp: segStart,
                  end_timestamp: segEnd,
                },
              };
                const segTrack = defineCreatedAnnotation(
                entity,
                features,
                trackShape,
                trackShape.viewRef,
                manifest,
                isVideo,
                currentFrameIndex.value,
              );
              if (!segTrack) return;
              segTrack.ui.displayControl = { hidden: false, editing: false, highlighted: "all" };
              (segTrack as Tracklet).ui.childs = [...segBBoxes];
              (segTrack as Tracklet).ui.childs.sort(sortByFrameIndex);
              saveTo("add", segTrack);
              entity.ui.childs?.push(segTrack);
              newTracks.push(segTrack);
            }
          }
        }
      } else {
        // Single keyframe or no tracker: create a single tracklet
        const trackStartFrame = currentFrameIndex.value;
        const candidate_tracks = entity.ui.childs?.filter(
          (ann) =>
            ann.is_type(BaseSchema.Tracklet) &&
            ann.data.view_name === newShape.value.viewRef.name &&
            (ann as Tracklet).data.start_frame <= trackStartFrame &&
            (ann as Tracklet).data.end_frame >= lastFrameIndex,
        );
        if (candidate_tracks && candidate_tracks.length === 1) {
          const candidate_track = candidate_tracks[0] as Tracklet;
          candidate_track.ui.childs.push(newAnnotation);
          if (isFromTracking) {
            for (const tr_mask of tracking_masks) candidate_track.ui.childs.push(tr_mask);
          }
          candidate_track.ui.childs.sort(sortByFrameIndex);
        } else {
          const trackShape: SaveTrackShape = {
            type: ShapeType.track,
            status: newShape.value.status,
            itemId: "",
            imageWidth: 0,
            imageHeight: 0,
            viewRef: { id: "", name: newShape.value.viewRef.name },
            attrs: {
              start_frame: trackStartFrame,
              end_frame: lastFrameIndex,
              start_timestamp: trackStartFrame,
              end_timestamp: lastFrameIndex,
            },
          };
          newTrack = defineCreatedAnnotation(
            entity,
            features,
            trackShape,
            trackShape.viewRef,
            manifest,
            isVideo,
            currentFrameIndex.value,
          );
          if (!newTrack) return;
          newTrack.ui.displayControl = { hidden: false, editing: false, highlighted: "all" };
          (newTrack as Tracklet).ui.childs = [newAnnotation];
          if (isFromTracking) {
            for (const tr_mask of tracking_masks) (newTrack as Tracklet).ui.childs.push(tr_mask);
          }
          (newTrack as Tracklet).ui.childs.sort(sortByFrameIndex);
          saveTo("add", newTrack);
          entity.ui.childs?.push(newTrack);
        }
      }

      // Save each tracking keyframe BBox
      for (const kfBBox of trackingKeyframeBBoxes) {
        saveTo("add", kfBBox);
      }

      // Clean up tracking session
      if (tracker !== null) {
        cancelTrackingSession();
      }
    }

    if (!entities.value.includes(entity)) {
      saveTo("add", entity);
    }

    saveTo("add", newAnnotation);

    if (isFromTracking) {
      for (const tr_mask of tracking_masks) {
        saveTo("add", tr_mask);
      }
    }

    // push new entity
    entities.update((ents) => {
      if (!ents.includes(entity)) ents.push(entity);
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
        ...(newTrack ? [newTrack] : []),
        ...newTracks,
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

  // Cleanup: remove temporary text span when this component unmounts
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
      <Button.Root type="button" class={cn(defaultButtonClass)} onclick={handleCancel}>Cancel</Button.Root>
      <Button.Root type="submit" class={cn(defaultButtonClass)} disabled={!isFormValid}>Confirm</Button.Root>
    </div>
  </form>
{/if}
<svelte:window onkeydown={handleKeyDown} />
