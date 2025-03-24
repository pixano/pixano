<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Loader2Icon } from "lucide-svelte";

  import type { FeaturesValues, SequenceFrame } from "@pixano/core";
  import {
    Annotation,
    BaseSchema,
    DatasetItem,
    Entity,
    isSequenceFrameArray,
    Mask,
    Tracklet,
    WorkspaceType,
    type SaveItem,
  } from "@pixano/core";

  import { rleFrString, rleToString } from "../../canvas2d/src/api/maskApi";
  import DatasetItemViewer from "./components/DatasetItemViewer/DatasetItemViewer.svelte";
  import Inspector from "./components/Inspector/InspectorInspector.svelte";
  import LoadModelModal from "./components/LoadModelModal.svelte";

  import "./index.css";

  import { getTopEntity } from "./lib/api/objectsApi";
  import { sortByFrameIndex } from "./lib/api/videoApi";
  import {
    annotations,
    canSave,
    entities,
    itemMetas,
    mediaViews,
    newShape,
    saveData,
    views,
  } from "./lib/stores/datasetItemWorkspaceStores";
  import { videoControls } from "./lib/stores/videoViewerStores";

  export let featureValues: FeaturesValues;
  export let selectedItem: DatasetItem;
  export let models: string[] = [];
  export let handleSaveItem: (data: SaveItem[]) => Promise<void>;
  export let isLoading: boolean;
  export let canSaveCurrentItem: boolean;
  export let shouldSaveCurrentItem: boolean;

  let isSaving: boolean = false;

  const back2front = (ann: Annotation): Annotation => {
    ann.ui = {
      datasetItemType: selectedItem.ui.type,
      displayControl: { hidden: false, editing: false },
    };
    if (ann.table_info.base_schema === BaseSchema.Mask) {
      //unpack Compressed RLE to uncompressed RLE
      const mask: Mask = ann as Mask;
      if (typeof mask.data.counts === "string") mask.data.counts = rleFrString(mask.data.counts);
    }
    if (selectedItem.ui.type === WorkspaceType.VIDEO) {
      //add frame_index to annotation
      if (ann.table_info.base_schema !== BaseSchema.Tracklet) {
        const seqframe = ($mediaViews[ann.data.view_ref.name] as SequenceFrame[]).find(
          (sf) => sf.id === ann.data.view_ref.id,
        );
        if (seqframe?.data.frame_index != undefined) ann.ui.frame_index = seqframe.data.frame_index;
      }
    }
    return ann;
  };

  const loadData = () => {
    views.set(selectedItem.views);

    if (selectedItem.ui.type === WorkspaceType.VIDEO) {
      for (const view in selectedItem.views) {
        if (isSequenceFrameArray(selectedItem.views[view])) {
          const video = selectedItem.views[view];
          const vspeed = Math.round(
            (video[video.length - 1].data.timestamp - video[0].data.timestamp) / video.length,
          );
          videoControls.update((old) => ({ ...old, videoSpeed: vspeed }));
        }
      }
    }

    const newAnns: Annotation[] = [];
    Object.values(selectedItem.annotations).forEach((anns) => {
      anns.forEach((ann) => newAnns.push(back2front(ann)));
    });
    //sort by frame_index (if present) -- some function (interpolation mostly) requires sorted annotations
    newAnns.sort((a, b) => sortByFrameIndex(a, b));
    annotations.set(newAnns);

    let newEntities: Entity[] = [];
    const subEntitiesChilds: Record<string, Annotation[]> = {};
    Object.values(selectedItem.entities).forEach((item_entities) => {
      item_entities.forEach((entity) => {
        //build childs list
        entity.ui = {
          ...entity.ui,
          childs: $annotations.filter((ann) => ann.data.entity_ref.id === entity.id),
        };
        newEntities.push(entity);
        if (entity.data.parent_ref.id !== "" && entity.ui.childs) {
          if (entity.data.parent_ref.id in subEntitiesChilds) {
            subEntitiesChilds[entity.data.parent_ref.id] = subEntitiesChilds[
              entity.data.parent_ref.id
            ].concat(entity.ui.childs);
          } else {
            subEntitiesChilds[entity.data.parent_ref.id] = entity.ui.childs;
          }
        }
      });
    });
    if (Object.keys(subEntitiesChilds).length > 0) {
      newEntities = newEntities.map((entity) => {
        if (entity.is_track && entity.id in subEntitiesChilds) {
          entity.ui.childs = [...entity.ui.childs!, ...subEntitiesChilds[entity.id]];
        }
        return entity;
      });
    }
    entities.set(newEntities);

    //add tracklets childs & all annotations top_entity
    annotations.update((anns) =>
      anns.map((ann) => {
        const top_entity = getTopEntity(ann);
        if (ann.is_type(BaseSchema.Tracklet)) {
          const tracklet = ann as Tracklet;
          if (top_entity) {
            tracklet.ui.childs =
              top_entity.ui.childs?.filter(
                (child) =>
                  child.ui.frame_index !== undefined &&
                  child.ui.frame_index <= tracklet.data.end_timestep &&
                  child.ui.frame_index >= tracklet.data.start_timestep &&
                  child.data.view_ref.name === tracklet.data.view_ref.name,
              ) || [];
            tracklet.ui.childs.sort((a, b) => a.ui.frame_index! - b.ui.frame_index!);
          }
        }
        return ann;
      }),
    );

    console.log("XXX entities", $entities);
    console.log("XXX annotations", $annotations);

    itemMetas.set({
      featuresList: featureValues || { main: {}, objects: {} },
      item: selectedItem.item,
      type: selectedItem.ui.type,
    });

    saveData.set([]);
  };

  canSave.subscribe((value) => (canSaveCurrentItem = value));

  $: if (selectedItem) {
    newShape.update((old) => ({ ...old, status: "none" }));
    loadData();
  }

  const front2back = (objs: SaveItem[]): SaveItem[] => {
    const backObjs: SaveItem[] = [];
    for (const obj of objs) {
      //mask: URLE to CompressedRLE
      if (
        (obj.change_type === "add" || obj.change_type === "update") &&
        obj.object.table_info.group === "annotations" &&
        obj.object.table_info.base_schema === BaseSchema.Mask &&
        Array.isArray((obj.object as Mask).data.counts)
      ) {
        const mask = structuredClone(obj.object) as Mask;
        mask.data.counts = rleToString(mask.data.counts as number[]);
        backObjs.push({ ...obj, object: mask });
      } else {
        backObjs.push({ ...obj });
      }
    }
    return backObjs;
  };

  //TMP log save data
  saveData.subscribe((save_data) => console.log("Change in SaveData", save_data));

  const onSave = async () => {
    isSaving = true;
    await handleSaveItem(front2back($saveData));
    saveData.set([]);
    isSaving = false;
  };

  $: {
    if (shouldSaveCurrentItem) {
      onSave().catch((err) => console.error(err));
    }
  }
</script>

<div class="flex-1 grid grid-cols-[calc(100%-380px)_380px]">
  {#if isSaving}
    <div
      class="h-full w-full flex justify-center items-center absolute top-0 left-0 bg-slate-300 z-50 opacity-30"
    >
      <Loader2Icon class="animate-spin" />
    </div>
  {/if}
  <DatasetItemViewer {selectedItem} {isLoading} />
  <Inspector on:click={onSave} {isLoading} />
  <LoadModelModal {models} />
</div>
