<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import type { FeaturesValues, DatasetItemSave, VideoObject } from "@pixano/core";
  import {
    Annotation,
    // BBox,
    // Keypoints,
    Mask,
    Entity,
    DatasetItem,
  } from "@pixano/core";

  import { rleFrString, rleToString } from "../../canvas2d/src/api/maskApi";
  import Toolbar from "./components/Toolbar.svelte";
  import Inspector from "./components/Inspector/InspectorInspector.svelte";
  import LoadModelModal from "./components/LoadModelModal.svelte";
  import {
    annotations,
    itemMetas,
    newShape,
    canSave,
    saveData,
    entities,
  } from "./lib/stores/datasetItemWorkspaceStores";
  import "./index.css";
  import type { Embeddings } from "./lib/types/datasetItemWorkspaceTypes";
  import DatasetItemViewer from "./components/DatasetItemViewer/DatasetItemViewer.svelte";
  import { Loader2Icon } from "lucide-svelte";
  import Keypoint from "@pixano/canvas2d/src/components/keypoints/Keypoint.svelte";

  export let featureValues: FeaturesValues;
  export let selectedItem: DatasetItem;
  export let models: string[] = [];
  export let handleSaveItem: (item: DatasetItemSave) => Promise<void>;
  export let isLoading: boolean;
  export let canSaveCurrentItem: boolean;
  export let shouldSaveCurrentItem: boolean;
  export let headerHeight: number = 0;

  let isSaving: boolean = false;

  let embeddings: Embeddings = {};

  const backToFrontAdapt = (ann: Annotation): Annotation => {
    //find corresponding entity
    // Object.values(selectedItem.entities).forEach((entities) => {
    //   for (const entity of entities) {
    //     if (entity.id === ann.data.entity_ref.id) {
    //       ann.features = {
    //         name: { name: "name", dtype: "str", value: entity.data["name"] as string },
    //       };
    //     }
    //   }
    // });
    //TMP: my dataset doesn't have source name yet...
    if (ann.data.source_ref.name == "") ann.data.source_ref.name = "Ground Truth"; //TMP

    // put type and data in corresponding field (aka bbox, keypoiints or mask)
    // adapt data model from back to front
    if (selectedItem.type === "image") {
      ann.datasetItemType = "image";
      if (ann.table_info.base_schema === "BBox") {
        //const bbox: BBox = ann as BBox;
        //nothing to do  ... (COOL!!)
      } else if (ann.table_info.base_schema === "KeyPoints") {
        //const kpt: Keypoints = ann as Keypoints;
        //nothing to do  ... (COOL!!)
      } else if (ann.table_info.base_schema === "CompressedRLE") {
        const mask: Mask = ann as Mask;
        if (typeof mask.data.counts === "string") mask.data.counts = rleFrString(mask.data.counts);
      }
    } else {
      ann.datasetItemType = "video";
      // if (ann.is_bbox) (ann as VideoObject).boxes?.push(ann.data);
      // else if (ann.is_keypoints)
      //   (ann as VideoObject).keypoints?.push(ann.data);
      //else if (ann.is_mask) (ann as VideoObject).mask = ann.data;
      //else if (ann.table_info.base_schema === "Tracklet") (ann as VideoObject).?? = ann.data;
      (ann as VideoObject).track = []; //TMP required to display video (but nothing else yet)
    }
    //delete ann.data;

    console.log("XXX backToFront", ann);

    return ann;
  };

  $: annotations.update((oldObjects) => {
    const newObjects: Annotation[] = [];
    for (const anns of Object.values(selectedItem.annotations)) {
      newObjects.push(
        ...anns.map((ann) => {
          const oldObject = oldObjects.find((o) => o.id === ann.id);
          if (oldObject) {
            return { ...oldObject, ...ann } as Annotation;
          }
          //if not already in annotations, it's a new object from back
          //TMP before UI datamodel rework, we map back datamodel to front datamodel
          return backToFrontAdapt(ann);
        }),
      );
    }
    return newObjects;
  });

  $: entities.update((oldObjects) => {
    const newObjects: Entity[] = [];
    for (const sel_entities of Object.values(selectedItem.entities)) {
      newObjects.push(
        ...sel_entities.map((entity) => {
          const oldObject = oldObjects.find((o) => o.id === entity.id);
          if (oldObject) {
            return { ...oldObject, ...entity } as Entity;
          }
          return entity;
        }),
      );
    }
    return newObjects;
  });

  $: console.log("XXX entities", $entities);

  $: itemMetas.set({
    mainFeatures: selectedItem.features,
    objectFeatures: Object.values(selectedItem.annotations || {})[0]?.features,
    featuresList: featureValues || { main: {}, objects: {} },
    views: selectedItem.views,
    id: selectedItem.id,
    type: selectedItem.type,
  });

  canSave.subscribe((value) => (canSaveCurrentItem = value));

  $: {
    if (selectedItem) {
      newShape.update((old) => ({ ...old, status: "none" }));
      canSave.set(false);
    }
  }

  //$: console.log("Change in SaveData", $saveData);

  const onSave = async () => {
    isSaving = true;
    const savedItem: DatasetItemSave = {
      id: selectedItem.id,
      split: "split" in selectedItem ? (selectedItem.split as string) : "undefined",
      save_data: $saveData,
      item_features: $itemMetas.mainFeatures,
    };
    await handleSaveItem(savedItem);
    saveData.set([]);
    canSave.set(false);
    isSaving = false;
  };

  $: {
    if (shouldSaveCurrentItem) {
      onSave().catch((err) => console.error(err));
    }
  }
</script>

<div class="w-full h-full grid grid-cols-[48px_calc(100%-380px-48px)_380px]">
  {#if isSaving}
    <div
      class="h-full w-full flex justify-center items-center absolute top-0 left-0 bg-slate-300 z-50 opacity-30"
    >
      <Loader2Icon class="animate-spin" />
    </div>
  {/if}
  <Toolbar />
  <DatasetItemViewer {selectedItem} {embeddings} {isLoading} {headerHeight} />
  <Inspector on:click={onSave} {isLoading} />
  <LoadModelModal
    {models}
    currentDatasetId={selectedItem.datasetId}
    selectedItemId={selectedItem.id}
    bind:embeddings
  />
</div>
