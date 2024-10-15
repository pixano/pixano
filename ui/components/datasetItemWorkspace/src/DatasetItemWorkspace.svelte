<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { onMount } from "svelte";
  import type { FeaturesValues } from "@pixano/core";
  import {
    Annotation,
    // BBox,
    // Keypoints,
    Mask,
    Entity,
    DatasetItem,
    Item,
    BaseData,
    type SaveItem,
    type Schema,
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
    views,
  } from "./lib/stores/datasetItemWorkspaceStores";
  import "./index.css";
  import type { Embeddings } from "./lib/types/datasetItemWorkspaceTypes";
  import DatasetItemViewer from "./components/DatasetItemViewer/DatasetItemViewer.svelte";
  import { Loader2Icon } from "lucide-svelte";
  import Keypoint from "@pixano/canvas2d/src/components/keypoints/Keypoint.svelte";

  export let featureValues: FeaturesValues;
  export let selectedItem: DatasetItem;
  export let models: string[] = [];
  export let handleSaveItem: (data: SaveItem[]) => Promise<void>;
  export let isLoading: boolean;
  export let canSaveCurrentItem: boolean;
  export let shouldSaveCurrentItem: boolean;
  export let headerHeight: number = 0;

  let isSaving: boolean = false;

  let embeddings: Embeddings = {};

  const back2front = (ann: Annotation): Annotation => {
    //TMP: my dataset doesn't have source name yet...
    if (ann.data.source_ref.name == "" || ann.data.source_ref.name == "source")
      ann.data.source_ref.name = "Ground Truth"; //TMP

    // put type and data in corresponding field (aka bbox, keypoiints or mask)
    // adapt data model from back to front
    if (selectedItem.type === "image") {
      ann.datasetItemType = "image";
      if (ann.table_info.base_schema === "CompressedRLE") {
        const mask: Mask = ann as Mask;
        if (typeof mask.data.counts === "string") mask.data.counts = rleFrString(mask.data.counts);
      }
    } else {
      ann.datasetItemType = "video";
      //add frame_index to annotation
      for (const view of Object.values($views)) {
        if (Array.isArray(view)) {
          const frame_index = view.find((sf) => sf.id === ann.data.view_ref.id)?.data.frame_index;
          ann.frame_index = frame_index;
        }
      }
      if (ann.table_info.base_schema === "CompressedRLE") {
        const mask: Mask = ann as Mask;
        if (typeof mask.data.counts === "string") mask.data.counts = rleFrString(mask.data.counts);
      }
    }
    return ann;
  };

  onMount(() => {
    views.set(selectedItem.views);

    const newAnns: Annotation[] = [];
    Object.values(selectedItem.annotations).forEach((anns) => {
      anns.forEach((ann) => newAnns.push(back2front(ann)));
    });
    annotations.set(newAnns);
    console.log("XXX annotations", $annotations);

    const newEntities: Entity[] = [];
    Object.values(selectedItem.entities).forEach((sel_entities) => {
      sel_entities.forEach((entity) => {
        //build childs list
        entity.childs = $annotations.filter((ann) => ann.data.entity_ref.id === entity.id);
        newEntities.push(entity);
      });
    });
    entities.set(newEntities);
    console.log("XXX entities", $entities);

    itemMetas.set({
      featuresList: featureValues || { main: {}, objects: {} },
      item: selectedItem.item,
      type: selectedItem.type,
    });
  });

  canSave.subscribe((value) => (canSaveCurrentItem = value));

  $: if (selectedItem) {
    newShape.update((old) => ({ ...old, status: "none" }));
    canSave.set(false);
  }

  export const front2back = (objs: SaveItem[]): SaveItem[] => {
    const backObjs: SaveItem[] = [];
    for (const obj of objs) {
      const schema = structuredClone(obj.object);
      //source_ref
      schema.data.source_ref = { name: "source", id: "" };
      //mask: URLE to CompressedRLE
      if (
        (obj.change_type === "add" || obj.change_type === "update") &&
        schema.table_info.group === "annotations" &&
        schema.table_info.base_schema === "CompressedRLE" &&
        Array.isArray((schema as Mask).data.counts)
      ) {
        const mask = schema as Mask;
        mask.data.counts = rleToString(mask.data.counts as number[]);
      }

      backObjs.push({ ...obj, object: schema });
    }
    return backObjs;
  };

  //TMP log save data
  saveData.subscribe((save_data) => console.log("Change in SaveData", save_data));

  const onSave = async () => {
    isSaving = true;
    await handleSaveItem(front2back($saveData));
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
    selectedItemId={selectedItem.item.id}
    bind:embeddings
  />
</div>
