<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Button, SequenceFrame, type SaveShape, type SaveTrackletShape } from "@pixano/core/src";

  import { Annotation, Entity, Tracklet, type Shape, type SaveItem } from "@pixano/core";

  import {
    newShape,
    annotations,
    entities,
    views,
    itemMetas,
    saveData,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import { datasetSchema } from "../../../../../apps/pixano/src/lib/stores/datasetStores";
  import type {
    CreateObjectInputs,
    ObjectProperties,
  } from "../../lib/types/datasetItemWorkspaceTypes";
  import { mapShapeInputsToFeatures, addNewInput } from "../../lib/api/featuresApi";
  import CreateFeatureInputs from "../Features/CreateFeatureInputs.svelte";
  import { currentFrameIndex } from "../../lib/stores/videoViewerStores";
  import {
    defineCreatedObject,
    defineCreatedEntity,
    addOrUpdateSaveItem,
  } from "../../lib/api/objectsApi";
  import { sortByFrameIndex } from "../../lib/api/videoApi";

  export let currentTab: "scene" | "objects";
  let shape: Shape;
  let isFormValid: boolean = false;
  let formInputs: CreateObjectInputs = [];

  let objectProperties: ObjectProperties = {};

  newShape.subscribe((value) => {
    if (value) shape = value;
  });

  const handleFormSubmit = () => {
    let newObject: Annotation | undefined = undefined;
    let newObject2: Annotation | undefined = undefined;
    let newTracklet: Annotation | undefined = undefined;
    let newEntity: Entity | undefined = undefined;
    const features = mapShapeInputsToFeatures(objectProperties, formInputs);
    const isVideo = $itemMetas.type === "video";
    if (shape.status === "saving") {
      newEntity = defineCreatedEntity(shape, features, $datasetSchema, isVideo);
      newEntity.ui.childs = [];
      newObject = defineCreatedObject(
        newEntity,
        shape,
        shape.viewRef,
        $datasetSchema,
        isVideo,
        $currentFrameIndex,
      );
      if (!newObject) return;
      newObject.ui.highlighted = "self";
      newObject.ui.displayControl = { editing: true };
      newEntity.ui.childs.push(newObject);
      if (newObject) {
        if (newObject.ui.datasetItemType === "video") {
          // for video, there is 2 anns, 1 track, 1 tracklet: add obj2 and tracklet
          let endFrameIndex = $currentFrameIndex + 5 + 1; //+1 for the first while loop
          //get view at endFrameIndex. If doesn't exist, get last possible one (range 5 down to 0)
          const seqs = $views[shape.viewRef.name];
          let endView: SequenceFrame | undefined = undefined;
          if (Array.isArray(seqs)) {
            while (!endView) {
              endFrameIndex = endFrameIndex - 1;
              endView = seqs.find(
                (view) =>
                  view.data.frame_index === endFrameIndex &&
                  view.table_info.name === (shape as SaveShape).viewRef.name,
              );
            }
          }
          newObject2 = defineCreatedObject(
            newEntity,
            shape,
            { id: endView!.id, name: shape.viewRef.name },
            $datasetSchema,
            isVideo,
            endFrameIndex,
          );
          if (!newObject2) return;
          newObject2.ui.highlighted = "none";
          newObject2.ui.displayControl = { editing: false };
          const trackletShape: SaveTrackletShape = {
            type: "tracklet",
            status: shape.status,
            itemId: "", //unused from SaveShapeBase
            imageWidth: 0, //unused from SaveShapeBase
            imageHeight: 0, //unused from SaveShapeBase
            viewRef: { id: "", name: shape.viewRef.name },
            attrs: {
              start_timestep: $currentFrameIndex,
              end_timestep: endFrameIndex,
              //TODO timestamp management...
              start_timestamp: $currentFrameIndex,
              end_timestamp: endFrameIndex,
            },
          };
          newTracklet = defineCreatedObject(
            newEntity,
            trackletShape,
            trackletShape.viewRef,
            $datasetSchema,
            isVideo,
            $currentFrameIndex,
          );
          if (!newTracklet) return;
          newTracklet.ui.highlighted = "none";
          newTracklet.ui.displayControl = { editing: false };
          (newTracklet as Tracklet).ui.childs = [newObject, newObject2];

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
          newEntity.ui.childs.push(newObject2);
          newEntity.ui.childs.push(newTracklet);
        }
        const save_item_entity: SaveItem = {
          change_type: "add",
          object: newEntity,
        };
        saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item_entity));
        const save_item: SaveItem = {
          change_type: "add",
          object: newObject,
        };
        saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
      }
      // push new entity
      entities.update((ents) => {
        if (newEntity) ents.push(newEntity);
        return ents;
      });
      //push new annotations
      annotations.update((oldObjects) => {
        const objectsWithoutHighlighted: Annotation[] = oldObjects.map((object) => {
          object.ui.highlighted = "none";
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
      for (let feat in objectProperties) {
        if (typeof objectProperties[feat] === "string") {
          addNewInput($itemMetas.featuresList, "objects", feat, objectProperties[feat]);
        }
      }
      newShape.set({ status: "none", shouldReset: true });
    }
    currentTab = "objects";
  };

  function handleKeyDown(event: KeyboardEvent) {
    if (event.key === "Escape") {
      newShape.set({ status: "none", shouldReset: true });
    }
  }
</script>

{#if shape.status === "saving"}
  <form class="flex flex-col gap-4 p-4" on:submit|preventDefault={handleFormSubmit}>
    <p>Save {shape.type}</p>
    <div class="max-h-[calc(100vh-250px)] overflow-y-auto flex flex-col gap-4">
      <CreateFeatureInputs bind:isFormValid bind:formInputs bind:objectProperties />
    </div>
    <div class="flex gap-4">
      <Button
        class="text-white"
        on:click={() => newShape.set({ status: "none", shouldReset: true })}>Cancel</Button
      >
      <Button class="text-white" type="submit" disabled={!isFormValid}>Confirm</Button>
    </div>
  </form>
{/if}
<svelte:window on:keydown={handleKeyDown} />
