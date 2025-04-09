<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  /* eslint-disable svelte/no-at-html-tags */
  // Imports
  import { onMount } from "svelte";

  import {
    Annotation,
    BaseSchema,
    Button,
    SaveShapeType,
    Tracklet,
    WorkspaceType,
    type SaveItem,
    type SaveTrackletShape,
  } from "@pixano/core";

  import { datasetSchema } from "../../../../../apps/pixano/src/lib/stores/datasetStores";
  import { addNewInput, mapShapeInputsToFeatures } from "../../lib/api/featuresApi";
  import {
    addOrUpdateSaveItem,
    defineCreatedObject,
    findOrCreateSubAndTopEntities,
  } from "../../lib/api/objectsApi";
  import { sortByFrameIndex } from "../../lib/api/videoApi";
  import { mapShapeType2BaseSchema } from "../../lib/constants";
  import {
    annotations,
    entities,
    itemMetas,
    newShape,
    saveData,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import { currentFrameIndex } from "../../lib/stores/videoViewerStores";
  import type {
    CreateObjectInputs,
    ObjectProperties,
  } from "../../lib/types/datasetItemWorkspaceTypes";
  import CreateFeatureInputs from "../Features/CreateFeatureInputs.svelte";
  import RelinkAnnotation from "./RelinkAnnotation.svelte";

  export let currentTab: "scene" | "objects";
  let isFormValid: boolean = false;
  let formInputs: CreateObjectInputs = [];

  let objectProperties: ObjectProperties = {};
  let selectedEntityId: string = "";

  const handleFormSubmit = () => {
    currentTab = "objects";

    if ($newShape.status !== "saving") {
      return;
    }

    let newObject: Annotation | undefined = undefined;
    let newTracklet: Annotation | undefined = undefined;

    const isVideo = $itemMetas.type === WorkspaceType.VIDEO;

    const features = mapShapeInputsToFeatures(objectProperties, formInputs);

    const { topEntity, subEntity } = findOrCreateSubAndTopEntities(
      selectedEntityId,
      $newShape,
      features,
    );

    newObject = defineCreatedObject(
      subEntity ?? topEntity,
      features,
      $newShape,
      $newShape.viewRef,
      $datasetSchema,
      isVideo,
      $currentFrameIndex,
    );

    if (!newObject) return;

    newObject.ui.displayControl = { hidden: false, editing: false, highlighted: "self" };
    newObject.ui.top_entities = subEntity ? [topEntity, subEntity] : [topEntity];
    topEntity.ui.childs?.push(newObject);

    if (subEntity) subEntity.ui.childs?.push(newObject);

    if (isVideo) {
      // for video, there is 1 anns, 1 track (may have 1 sub entity), 1 tracklet
      // -> add tracklet
      const candidate_tracklets = topEntity.ui.childs?.filter(
        (ann) =>
          ann.is_type(BaseSchema.Tracklet) &&
          ann.data.view_ref.name === $newShape.viewRef.name &&
          (ann as Tracklet).data.start_timestep <= $currentFrameIndex &&
          (ann as Tracklet).data.end_timestep >= $currentFrameIndex,
      );
      if (candidate_tracklets && candidate_tracklets.length === 1) {
        const candidate_tracklet = candidate_tracklets[0] as Tracklet;
        //NOTE: we add the new object "as it is" in the candidate tracklet
        //it means that the tracklet may be wider than the new shape "range" (1 frame at creation)
        //-- this is potentially dangerous... but *should* be fine --
        candidate_tracklet.ui.childs.push(newObject);
        candidate_tracklet.ui.childs.sort(sortByFrameIndex);
      } else {
        const trackletShape: SaveTrackletShape = {
          type: SaveShapeType.tracklet,
          status: $newShape.status,
          itemId: "", //unused from SaveShapeBase
          imageWidth: 0, //unused from SaveShapeBase
          imageHeight: 0, //unused from SaveShapeBase
          viewRef: { id: "", name: $newShape.viewRef.name },
          attrs: {
            start_timestep: $currentFrameIndex,
            end_timestep: $currentFrameIndex,
            //TODO timestamp management...
            start_timestamp: $currentFrameIndex,
            end_timestamp: $currentFrameIndex,
          },
        };
        newTracklet = defineCreatedObject(
          topEntity,
          features,
          trackletShape,
          trackletShape.viewRef,
          $datasetSchema,
          isVideo,
          $currentFrameIndex,
        );
        if (!newTracklet) return;
        newTracklet.ui.displayControl = { hidden: false, editing: false, highlighted: "all" };
        (newTracklet as Tracklet).ui.childs = [newObject];

        const save_item_tracklet: SaveItem = {
          change_type: "add",
          object: newTracklet,
        };
        saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item_tracklet));
        //TODO Note: we may have to manage "spatial object" entity too...
        topEntity.ui.childs?.push(newTracklet);
      }
    }

    if (!$entities.includes(topEntity)) {
      const save_item_entity: SaveItem = {
        change_type: "add",
        object: topEntity,
      };
      saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item_entity));
    }

    if (subEntity && !$entities.includes(subEntity)) {
      const save_subEntity: SaveItem = {
        change_type: "add",
        object: subEntity,
      };
      saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_subEntity));
    }

    const save_item: SaveItem = {
      change_type: "add",
      object: newObject,
    };

    saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
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
        ...(newObject ? [newObject] : []),
        ...(newTracklet ? [newTracklet] : []),
      ];
    });

    $annotations.sort((a, b) => sortByFrameIndex(a, b));
    for (const tname in objectProperties) {
      for (const feat in objectProperties[tname]) {
        if (typeof objectProperties[feat] === "string") {
          addNewInput($itemMetas.featuresList, "objects", feat, objectProperties[feat]);
        }
      }
    }

    newShape.set({ status: "none", shouldReset: true });
  };

  function handleKeyDown(event: KeyboardEvent) {
    if (event.key === "Escape") {
      newShape.set({ status: "none", shouldReset: true });
    }
  }

  //set specific header text for different kind of shape
  let saveText = "Save";
  onMount(() => {
    if ($newShape.status === "saving") {
      saveText = saveText + " " + $newShape.type;
      if ($newShape.type === SaveShapeType.textSpan) {
        saveText = saveText + " <i>" + $newShape.attrs.mention + "</i>";
      }
    }
  });
</script>

{#if $newShape.status === "saving"}
  <form class="flex flex-col gap-4 p-4" on:submit|preventDefault={handleFormSubmit}>
    <p>{@html saveText}</p>
    <RelinkAnnotation
      bind:selectedEntityId
      baseSchema={mapShapeType2BaseSchema[$newShape.type]}
      viewRef={$newShape.viewRef}
    />
    <div class="max-h-[calc(100vh-250px)] overflow-y-auto flex flex-col gap-4">
      <CreateFeatureInputs
        bind:isFormValid
        bind:formInputs
        bind:objectProperties
        baseSchema={mapShapeType2BaseSchema[$newShape.type]}
      />
    </div>
    <div class="flex gap-4">
      <Button
        class="text-white"
        on:click={() => newShape.set({ status: "none", shouldReset: true })}
      >
        Cancel
      </Button>
      <Button class="text-white" type="submit" disabled={!isFormValid}>Confirm</Button>
    </div>
  </form>
{/if}
<svelte:window on:keydown={handleKeyDown} />
