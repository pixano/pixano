<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import {
    Annotation,
    BaseSchema,
    Entity,
    SequenceFrame,
    Track,
    Tracklet,
    type SaveItem,
    type SaveShape,
    type SaveTrackletShape,
  } from "@pixano/core";
  import { Button, SaveShapeType, type DS_NamedSchema, type ItemFeature } from "@pixano/core/src";
  import { derived } from "svelte/store";
  import { datasetSchema } from "../../../../../apps/pixano/src/lib/stores/datasetStores";
  import { addNewInput, mapShapeInputsToFeatures } from "../../lib/api/featuresApi";
  import {
    addOrUpdateSaveItem,
    defineCreatedEntity,
    defineCreatedObject,
  } from "../../lib/api/objectsApi";
  import { sortByFrameIndex } from "../../lib/api/videoApi";
  import {
    annotations,
    entities,
    itemMetas,
    newShape,
    saveData,
    views,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import { currentFrameIndex } from "../../lib/stores/videoViewerStores";
  import type {
    CreateObjectInputs,
    ObjectProperties,
  } from "../../lib/types/datasetItemWorkspaceTypes";
  import CreateFeatureInputs from "../Features/CreateFeatureInputs.svelte";
  export let currentTab: "scene" | "objects";
  let isFormValid: boolean = false;
  let formInputs: CreateObjectInputs = [];

  let objectProperties: ObjectProperties = {};
  let selectedEntityId: string = "";

  const mapShapeType2BaseSchema: Record<SaveShapeType, BaseSchema> = {
    bbox: BaseSchema.BBox,
    keypoints: BaseSchema.Keypoints,
    mask: BaseSchema.Mask,
    tracklet: BaseSchema.Tracklet,
    textSpan: BaseSchema.TextSpan,
  };

  const isEntityAllowedAsTop = (entity: Entity, shape: SaveShape) => {
    return (
      entity.data.parent_ref.id === "" && //not a sub entity
      (!entity.ui.childs
        ?.filter((ann) => !ann.is_tracklet)
        .some(
          (ann) =>
            ann.data.view_ref.id === shape.viewRef.id &&
            mapShapeType2BaseSchema[shape.type] === ann.table_info.base_schema,
        ) ||
        !entity.ui.childs
          ?.filter((ann) => ann.is_tracklet)
          .some(
            (ann) =>
              (ann as Tracklet).data.view_ref.name === shape.viewRef.name &&
              (ann as Tracklet).data.start_timestep < $currentFrameIndex + 6 &&
              (ann as Tracklet).data.end_timestep > $currentFrameIndex,
          ))
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

  const findOrCreateSubAndTopEntities = (
    shape: SaveShape,
    endView: SequenceFrame | undefined,
    features: Record<string, Record<string, ItemFeature>>,
  ): {
    topEntity: Entity | Track;
    subEntity: Entity | undefined;
    secondSubEntity: Entity | undefined;
  } => {
    //Manage sub-entity: check if there is some subentity table(s)
    //For video (if endView is set), we also find/create the 2nd sub-entity
    //if so, choose the correct one, and separate topEntity from subEntity ...
    //TMP: we should rely on "table relations" from $datasetSchema, but it's not available yet
    //TMP: so, we will make the assumption that the only case with subentity is : 1 Track + 1 Entity (sub)
    //TMP: -> we take trackSchemas[0] and entitySchemas[0]
    let topEntity: Entity | Track | undefined = undefined;
    let subEntity: Entity | undefined = undefined;
    let secondSubEntity: Entity | undefined = undefined;
    let topEntitySchema: DS_NamedSchema | undefined = undefined;
    let subEntitySchema: DS_NamedSchema | undefined = undefined;
    let trackSchemas: DS_NamedSchema[] = [];
    Object.entries($datasetSchema.schemas).forEach(([name, sch]) => {
      if (sch.base_schema === BaseSchema.Track) {
        trackSchemas.push({ ...sch, name });
      }
    });
    let entitySchemas: DS_NamedSchema[] = [];
    Object.entries($datasetSchema.schemas).forEach(([name, sch]) => {
      if (sch.base_schema === BaseSchema.Entity) entitySchemas.push({ ...sch, name });
    });
    if (trackSchemas.length > 0) {
      topEntitySchema = trackSchemas[0];
      if (entitySchemas.length > 0) {
        subEntitySchema = entitySchemas[0];
      }
    } else if (entitySchemas.length > 0) {
      topEntitySchema = entitySchemas[0];
    } else {
      console.error("ERROR: No available schema Entity", $datasetSchema.schemas);
      throw new Error("ERROR: No available schema Entity");
    }

    if (selectedEntityId === "new") {
      topEntity = defineCreatedEntity(
        shape,
        features[topEntitySchema.name],
        $datasetSchema,
        topEntitySchema,
      );
      topEntity.ui.childs = [];
      if (subEntitySchema) {
        subEntity = defineCreatedEntity(
          shape,
          features[subEntitySchema.name],
          $datasetSchema,
          subEntitySchema,
          {
            id: topEntity.id,
            name: topEntity.table_info.name,
          },
        );
        subEntity.ui.childs = [];
        if (endView) {
          secondSubEntity = defineCreatedEntity(
            shape,
            features[subEntitySchema.name],
            $datasetSchema,
            subEntitySchema,
            {
              id: topEntity.id,
              name: topEntity.table_info.name,
            },
            { id: endView.id, name: shape.viewRef.name },
          );
          secondSubEntity.ui.childs = [];
        }
      }
    } else {
      topEntity = $entities.find((entity) => entity.id === selectedEntityId);
      if (!topEntity) {
        topEntity = defineCreatedEntity(
          shape,
          features[topEntitySchema.name],
          $datasetSchema,
          topEntitySchema,
        );
        topEntity.ui.childs = [];
      }
      if (subEntitySchema) {
        //need to find entity with corresponding parent_ref.id and table_info.name, and view name
        subEntity = $entities.find(
          (entity) =>
            //need to find entity with corresponding parent_ref.id and table_info.name, and view name
            entity.table_info.name === subEntitySchema.name &&
            entity.table_info.base_schema === subEntitySchema.base_schema &&
            entity.data.parent_ref.id === topEntity!.id &&
            //badly, *sub*entity.data.view_ref (id, or at least name) is not always set (it should!)
            (entity.data.view_ref.id !== ""
              ? entity.data.view_ref.id === shape.viewRef.id
              : entity.data.view_ref.name !== ""
                ? entity.data.view_ref.name === shape.viewRef.name
                : entity.ui.childs?.every((ann) => ann.data.view_ref.name === shape.viewRef.name)),
        );
        if (!subEntity) {
          subEntity = defineCreatedEntity(
            shape,
            features[subEntitySchema.name],
            $datasetSchema,
            subEntitySchema,
            {
              id: topEntity.id,
              name: topEntity.table_info.name,
            },
          );
          subEntity.ui.childs = [];
        }
        if (endView) {
          secondSubEntity = $entities.find(
            (entity) =>
              //need to find entity with corresponding parent_ref.id and table_info.name, and view name
              entity.table_info.name === subEntitySchema.name &&
              entity.table_info.base_schema === subEntitySchema.base_schema &&
              entity.data.parent_ref.id === topEntity!.id &&
              //badly, *sub*entity.data.view_ref (id, or at least name) is not always set (it should!)
              (entity.data.view_ref.id !== ""
                ? entity.data.view_ref.id === endView.id
                : entity.data.view_ref.name !== ""
                  ? entity.data.view_ref.name === shape.viewRef.name
                  : entity.ui.childs?.every(
                      (ann) => ann.data.view_ref.name === shape.viewRef.name,
                    )),
          );
          if (!secondSubEntity) {
            secondSubEntity = defineCreatedEntity(
              shape,
              features[subEntitySchema.name],
              $datasetSchema,
              subEntitySchema,
              {
                id: topEntity.id,
                name: topEntity.table_info.name,
              },
              { id: endView.id, name: shape.viewRef.name },
            );
            secondSubEntity.ui.childs = [];
          }
        }
      }
    }
    return { topEntity, subEntity, secondSubEntity };
  };

  const handleFormSubmit = () => {
    currentTab = "objects";
    
    if ($newShape.status !== "saving") {
      return;
    }

    let newObject: Annotation | undefined = undefined;
    let newObject2: Annotation | undefined = undefined;
    let newTracklet: Annotation | undefined = undefined;

    const isVideo = $itemMetas.type === "video";

    let endView: SequenceFrame | undefined = undefined;
    let endFrameIndex: number = -1;

    if (isVideo) {
      endFrameIndex = $currentFrameIndex + 5 + 1; //+1 for the first while loop
      const seqs = $views[$newShape.viewRef.name];
      if (Array.isArray(seqs)) {
        while (!endView) {
          endFrameIndex = endFrameIndex - 1;
          endView = (seqs as SequenceFrame[]).find(
            (view) =>
              view.data.frame_index === endFrameIndex &&
              view.table_info.name === ($newShape as SaveShape).viewRef.name,
          );
        }
      }
    }
    
    const features = mapShapeInputsToFeatures(objectProperties, formInputs);

    const { topEntity, subEntity, secondSubEntity } = findOrCreateSubAndTopEntities(
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

    newObject.ui.highlighted = "self";
    newObject.ui.displayControl = { editing: false };
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
      newObject2.ui.highlighted = "self";
      newObject2.ui.displayControl = { editing: false };
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
      newTracklet.ui.highlighted = "none";
      newTracklet.ui.displayControl = { editing: false };
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
        baseSchema={mapShapeType2BaseSchema[$newShape.type]}
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
