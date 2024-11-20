<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { derived } from "svelte/store";
  import { Button } from "@pixano/core/src";
  import {
    Annotation,
    Entity,
    Tracklet,
    SequenceFrame,
    type SaveItem,
    type SaveShape,
    type SaveTrackletShape,
  } from "@pixano/core";
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
  let isFormValid: boolean = false;
  let formInputs: CreateObjectInputs = [];

  let objectProperties: ObjectProperties = {};
  let selectedEntityId: string = "";
  const mapShapeType2BaseSchema = {
    bbox: "BBox",
    keypoints: "KeyPoints",
    mask: "CompressedRLE",
    tracklet: "Tracklet",
  };

  const isEntityAllowedAsTop = (entity: Entity, shape: SaveShape) => {
    return !entity.ui.childs?.some(
      (ann) =>
        (ann.data.view_ref.id === shape.viewRef.id &&
          mapShapeType2BaseSchema[shape.type] === ann.table_info.base_schema) ||
        (ann.is_tracklet &&
          (ann as Tracklet).data.view_ref.name === shape.viewRef.name &&
          (ann as Tracklet).data.start_timestep < $currentFrameIndex + 6 &&
          (ann as Tracklet).data.end_timestep > $currentFrameIndex),
    );
  };

  let entitiesCombo = derived([entities, newShape], ([$entities, $newShape]) => {
    const res: { id: string; name: string }[] = [{ id: "new", name: "New" }];
    if ($newShape.status === "saving")
      $entities.forEach((entity) => {
        //check if there is no annotation of same kind & view_id for this entity
        if (isEntityAllowedAsTop(entity, $newShape))
          res.push({ id: entity.id, name: (entity.data.name as string) + " - " + entity.id });
      });
    selectedEntityId = res[0].id;
    return res;
  });

  const handleFormSubmit = () => {
    let newObject: Annotation | undefined = undefined;
    let newObject2: Annotation | undefined = undefined;
    let newTracklet: Annotation | undefined = undefined;
    let topEntity: Entity | undefined = undefined;
    const features = mapShapeInputsToFeatures(objectProperties, formInputs);
    const isVideo = $itemMetas.type === "video";
    if ($newShape.status === "saving") {
      if (selectedEntityId === "new") {
        topEntity = defineCreatedEntity($newShape, features, $datasetSchema, isVideo);
        topEntity.ui.childs = [];
      } else {
        topEntity = $entities.find((entity) => entity.id === selectedEntityId);
        if (!topEntity) {
          topEntity = defineCreatedEntity($newShape, features, $datasetSchema, isVideo);
          topEntity.ui.childs = [];
        }
      }
      //TODO: manage subentity for video: check if there is some subentity table(s)
      //if so, choose the correct one, and separate topEntity from subEntity ...
      newObject = defineCreatedObject(
        topEntity,
        $newShape,
        $newShape.viewRef,
        $datasetSchema,
        isVideo,
        $currentFrameIndex,
      );
      if (!newObject) return;
      newObject.ui.highlighted = "self";
      newObject.ui.displayControl = { editing: false };
      topEntity.ui.childs?.push(newObject);
      if (newObject.ui.datasetItemType === "video") {
        // for video, there is 2 anns, 1 track, 1 tracklet: add obj2 and tracklet
        let endFrameIndex = $currentFrameIndex + 5 + 1; //+1 for the first while loop
        //get view at endFrameIndex. If doesn't exist, get last possible one (range 5 down to 0)
        const seqs = $views[$newShape.viewRef.name];
        let endView: SequenceFrame | undefined = undefined;
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
        newObject2 = defineCreatedObject(
          topEntity,
          $newShape,
          { id: endView!.id, name: $newShape.viewRef.name },
          $datasetSchema,
          isVideo,
          endFrameIndex,
        );
        if (!newObject2) return;
        newObject2.ui.highlighted = "self";
        newObject2.ui.displayControl = { editing: false };
        const trackletShape: SaveTrackletShape = {
          type: "tracklet",
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
      const save_item: SaveItem = {
        change_type: "add",
        object: newObject,
      };
      saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
      // push new entity
      entities.update((ents) => {
        if (topEntity && !ents.includes(topEntity)) ents.push(topEntity);
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

{#if $newShape.status === "saving"}
  <form class="flex flex-col gap-4 p-4" on:submit|preventDefault={handleFormSubmit}>
    <p>Save {$newShape.type}</p>
    <div class="max-h-[calc(100vh-250px)] overflow-y-auto flex flex-col gap-4">
      <CreateFeatureInputs
        bind:isFormValid
        bind:formInputs
        bind:objectProperties
        entitiesCombo={$entitiesCombo}
        bind:selectedEntityId
      />
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
