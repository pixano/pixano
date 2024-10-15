<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Button } from "@pixano/core/src";

  import { Annotation, Entity, type Shape, type SaveItem } from "@pixano/core";

  import {
    newShape,
    annotations,
    entities,
    itemMetas,
    canSave,
    saveData,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import { datasetSchema } from "../../../../../apps/pixano/src/lib/stores/datasetStores";
  import type {
    CreateObjectInputs,
    ObjectProperties,
  } from "../../lib/types/datasetItemWorkspaceTypes";
  import { mapShapeInputsToFeatures, addNewInput } from "../../lib/api/featuresApi";
  import CreateFeatureInputs from "../Features/CreateFeatureInputs.svelte";
  import { currentFrameIndex, objectIdBeingEdited } from "../../lib/stores/videoViewerStores";
  import {
    defineCreatedObject,
    defineCreatedEntity,
    addOrUpdateSaveItem,
  } from "../../lib/api/objectsApi";

  export let currentTab: "scene" | "objects";
  let shape: Shape;
  let isFormValid: boolean = false;
  let formInputs: CreateObjectInputs = [];

  let objectProperties: ObjectProperties = {};

  newShape.subscribe((value) => {
    if (value) shape = value;
  });

  const handleFormSubmit = () => {
    const features = mapShapeInputsToFeatures(objectProperties, formInputs);
    let newObject: Annotation | null = null;
    let newEntity: Entity | null = null;
    annotations.update((oldObjects) => {
      if (shape.status !== "saving") return oldObjects;
      newEntity = defineCreatedEntity(shape, features, $datasetSchema);
      entities.update((ents) => {
        if (newEntity) ents.push(newEntity);
        return ents;
      });
      newObject = defineCreatedObject(
        newEntity,
        shape,
        $itemMetas.type,
        features,
        $currentFrameIndex,
      );
      objectIdBeingEdited.set(newObject?.id || null);
      const objectsWithoutHighlighted: Annotation[] = oldObjects.map((object) => {
        object.highlighted = "none";
        object.displayControl = { ...object.displayControl, editing: false };
        return object;
      });

      if (newObject) {
        console.log("ToSave (creation):", newObject, shape);
        if (newObject.datasetItemType === "video") {
          // for video, there is 2 bbox|keypoints, 1 track, 1 tracklet
          if (shape.type === "bbox" && newObject.is_bbox) {
            for (let box of newObject.data) {
              const save_item: SaveItem = {
                change_type: "add_or_update",
                kind: shape.type, //TODO correct kind //this should represent the annotation table to be refered...?
                data: { ...box, entity_ref: { id: newObject.id, name: "top_entity" } },
              };
              saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
            }
          }
          if (shape.type === "keypoints" && newObject.keypoints) {
            for (let kpt of newObject.keypoints) {
              const save_item: SaveItem = {
                change_type: "add_or_update",
                ref_name: shape.type, //this should represent the annotation table to be refered...?
                data: { ...kpt, entity_ref: { id: newObject.id, name: "top_entity" } },
              };
              saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
            }
          }
          //add Tracklet
          const save_item_tracklet: SaveItem = {
            change_type: "add_or_update",
            ref_name: "tracklet",
            data: {
              ...newObject.track[0],
              entity_ref: { id: newObject.id, name: "top_entity" },
            },
          };
          saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item_tracklet));
          //add Track
          const save_item_track: SaveItem = {
            change_type: "add_or_update",
            ref_name: "top_entity",
            data: {
              id: newObject.id,
              //item_id: newObject.item_id,
              source_ref: newObject.source_ref,
              features: newObject.features,
              view_id: newObject.track[0].view_id,
              entity_ref: { id: "", name: "" }, //no parent for track
              ref_name: "top_entity",
            },
          };
          saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item_track));
          //TODO Note: we may have to manage "spatial object" entity too...
        } else {
          const save_item: SaveItem = {
            change_type: "add",
            kind: "annotations",
            object: newObject,
          };
          saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
          const save_item_entity: SaveItem = {
            change_type: "add",
            kind: "entities",
            object: newEntity,
          };
          saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item_entity));
        }
      }
      return [...objectsWithoutHighlighted, ...(newObject ? [newObject] : [])];
    });

    for (let feat in objectProperties) {
      if (typeof objectProperties[feat] === "string") {
        addNewInput($itemMetas.featuresList, "objects", feat, objectProperties[feat] as string);
      }
    }
    newShape.set({ status: "none", shouldReset: true });
    canSave.set(true);
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
