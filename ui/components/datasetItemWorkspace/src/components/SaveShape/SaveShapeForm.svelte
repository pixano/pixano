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
    Button,
    SaveShapeType,
    SequenceFrame,
    Tracklet,
    WorkspaceType,
    type SaveItem,
    type SaveShape,
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
  import { mapShapeType2BaseSchema, NEWTRACKLET_LENGTH } from "../../lib/constants";
  import {
    annotations,
    entities,
    itemMetas,
    mediaViews,
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
    let newObject2: Annotation | undefined = undefined;
    let newTracklet: Annotation | undefined = undefined;

    const isVideo = $itemMetas.type === WorkspaceType.VIDEO;

    let endView: SequenceFrame | undefined = undefined;
    let endFrameIndex: number = -1;

    if (isVideo) {
      endFrameIndex = $currentFrameIndex + NEWTRACKLET_LENGTH + 1; //+1 for the first while loop
      const seqs = $mediaViews[$newShape.viewRef.name];
      if (Array.isArray(seqs)) {
        while (!endView) {
          endFrameIndex = endFrameIndex - 1;
          endView = seqs.find(
            (view) =>
              view.data.frame_index === endFrameIndex &&
              view.table_info.name === ($newShape as SaveShape).viewRef.name,
          );
        }
      }
    }

    const features = mapShapeInputsToFeatures(objectProperties, formInputs);

    const { topEntity, subEntity, secondSubEntity } = findOrCreateSubAndTopEntities(
      selectedEntityId,
      $newShape,
      endView,
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
    topEntity.ui.childs?.push(newObject);

    if (subEntity) subEntity.ui.childs?.push(newObject);

    if (isVideo) {
      // for video, there is 2 anns, 1 track (may have 1 sub entity per obj), 1 tracklet
      // -> add obj2 (+ eventual 2nd sub entity) and tracklet
      newObject2 = defineCreatedObject(
        secondSubEntity ? secondSubEntity : topEntity,
        features,
        $newShape,
        { id: endView!.id, name: $newShape.viewRef.name },
        $datasetSchema,
        isVideo,
        endFrameIndex,
      );
      if (!newObject2) return;
      newObject2.ui.displayControl = { hidden: false, editing: false, highlighted: "self" };
      //TODO: It is possible that a tracklet already exist (used for a different kind of shape)
      //For now, it always create a tracklet...
      //if so, we should found it, use it, and maybe adapt it (size? but need many check with neighbours etc.)
      //--> It would be far more easy to create 1 frame tracklet, and allow other means of tracklet edition
      const trackletShape: SaveTrackletShape = {
        type: SaveShapeType.tracklet,
        status: $newShape.status,
        itemId: "", //unused from SaveShapeBase
        imageWidth: 0, //unused from SaveShapeBase
        imageHeight: 0, //unused from SaveShapeBase
        viewRef: { id: "", name: $newShape.viewRef.name },
        attrs: {
          start_timestep: $currentFrameIndex,
          end_timestep: endFrameIndex,
          //TODO timestamp management...
          start_timestamp: $currentFrameIndex,
          end_timestamp: endFrameIndex,
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
      (newTracklet as Tracklet).ui.childs = [newObject, newObject2];

      if (secondSubEntity) {
        secondSubEntity.ui.childs?.push(newObject2);
        if (!$entities.includes(secondSubEntity)) {
          const save_2ndSubEntity: SaveItem = {
            change_type: "add",
            object: secondSubEntity,
          };
          saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_2ndSubEntity));
        }
      }
      const save_item2: SaveItem = {
        change_type: "add",
        object: newObject2,
      };
      saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item2));
      const save_item_tracklet: SaveItem = {
        change_type: "add",
        object: newTracklet,
      };
      saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item_tracklet));
      //TODO Note: we may have to manage "spatial object" entity too...
      topEntity.ui.childs?.push(newObject2);
      topEntity.ui.childs?.push(newTracklet);
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
      if (secondSubEntity && !ents.includes(secondSubEntity)) ents.push(secondSubEntity);
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
        ...(newObject2 ? [newObject2] : []),
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
    <RelinkAnnotation bind:selectedEntityId viewRef={$newShape.viewRef} />
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
