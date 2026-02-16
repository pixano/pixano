<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Loader2Icon, SaveIcon, ShieldAlertIcon, XIcon } from "lucide-svelte";
  import { nanoid } from "nanoid";
  import { cubicOut } from "svelte/easing";
  import { fade, fly } from "svelte/transition";

  import type { FeaturesValues, SequenceFrame } from "@pixano/core";
  import {
    Annotation,
    BaseSchema,
    BBox,
    Button,
    DatasetItem,
    Entity,
    initDisplayControl,
    isSequenceFrameArray,
    Mask,
    Tracklet,
    WorkspaceType,
    type BBoxType,
    type SaveItem,
  } from "@pixano/core";
  import { mask_utils } from "@pixano/models";

  import {
    getBoundingBoxFromMaskSVG,
    rleFrString,
    rleToString,
  } from "../../canvas2d/src/api/maskApi";
  import DatasetItemViewer from "./components/DatasetItemViewer/DatasetItemViewer.svelte";
  import Inspector from "./components/Inspector/InspectorInspector.svelte";
  import LoadModelModal from "./components/LoadModelModal.svelte";

  import "./index.css";

  import { onDestroy } from "svelte";

  import { addOrUpdateSaveItem, getTopEntity } from "./lib/api/objectsApi";
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
  export let handleSaveItem: (data: SaveItem[]) => Promise<void>;
  export let isLoading: boolean;
  export let canSaveCurrentItem: boolean;
  export let shouldSaveCurrentItem: boolean;

  // utility vars for resizing with slide bar
  const defaultOIWidth = 450;
  let objectInspectorAreaMaxWidth = defaultOIWidth; //default width
  const minOIAreaWidth = 0; //minimum width for ObjectInspector area
  let initialOIAreaX = 0;
  let initialOIAreaWidth = 0;

  let isSaving: boolean = false;
  let showAutogenBBoxAlert = false;

  const back2front = (ann: Annotation): Annotation => {
    ann.ui = { datasetItemType: selectedItem.ui.type, displayControl: initDisplayControl };
    if (ann.table_info.base_schema === BaseSchema.Mask) {
      //unpack Compressed RLE to uncompressed RLE
      const mask: Mask = ann as Mask;
      if (typeof mask.data.counts === "string") mask.data.counts = rleFrString(mask.data.counts);
      if (!mask.ui.svg) {
        const rle = mask.data.counts;
        const size = mask.data.size;
        const maskPoly = mask_utils.generatePolygonSegments(rle, size[0]);
        mask.ui.svg = mask_utils.convertSegmentsToSVG(maskPoly);
      }
    }
    if (selectedItem.ui.type === WorkspaceType.VIDEO) {
      //add frame_index to annotation
      if (ann.table_info.base_schema !== BaseSchema.Tracklet) {
        const seqframe = ($mediaViews[ann.data.view_ref.name] as SequenceFrame[]).find(
          (sf) => sf.id === ann.data.view_ref.id,
        );
        if (seqframe?.data.frame_index !== undefined)
          ann.ui.frame_index = seqframe.data.frame_index;
      }
    }
    return ann;
  };

  const loadData = () => {
    saveData.set([]);
    showAutogenBBoxAlert = false;
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

    // Automatically generate missing bounding boxes for masks
    const generatedBBoxes: BBox[] = [];
    const bboxTableNames = Object.keys(selectedItem.annotations).filter((name) =>
      name.toLowerCase().includes("bbox"),
    );
    const defaultBBoxTable = bboxTableNames.length > 0 ? bboxTableNames[0] : null;

    newAnns.forEach((ann) => {
      if (ann.is_type(BaseSchema.Mask)) {
        const mask = ann as Mask;
        const hasBBox = newAnns.some(
          (other) =>
            other.is_type(BaseSchema.BBox) &&
            other.data.entity_ref.id === mask.data.entity_ref.id &&
            other.data.view_ref.id === mask.data.view_ref.id &&
            other.data.view_ref.name === mask.data.view_ref.name,
        );

        if (!hasBBox) {
          const bboxCoords = getBoundingBoxFromMaskSVG(mask.ui.svg);
          if (bboxCoords) {
            const now = new Date(Date.now()).toISOString().replace(/Z$/, "+00:00");
            const bboxData: BBoxType = {
              item_ref: mask.data.item_ref,
              view_ref: mask.data.view_ref,
              entity_ref: mask.data.entity_ref,
              source_ref: mask.data.source_ref,
              inference_metadata: {},
              coords: [bboxCoords.x, bboxCoords.y, bboxCoords.width, bboxCoords.height],
              format: "xywh",
              is_normalized: false,
              confidence: 1,
            };

            const newBBox = new BBox({
              id: nanoid(10),
              created_at: now,
              updated_at: now,
              table_info: {
                name: defaultBBoxTable || mask.table_info.name.replace("mask", "bbox"),
                group: "annotations",
                base_schema: BaseSchema.BBox,
              },
              data: bboxData,
            });
            newBBox.ui = {
              datasetItemType: mask.ui.datasetItemType,
              displayControl: { ...initDisplayControl, highlighted: "none" },
              frame_index: mask.ui.frame_index,
            };
            generatedBBoxes.push(newBBox);
          }
        }
      }
    });

    if (generatedBBoxes.length > 0) {
      newAnns.push(...generatedBBoxes);
      showAutogenBBoxAlert = true;
      saveData.update((current_sd) => {
        let updated = current_sd;
        generatedBBoxes.forEach((bbox) => {
          updated = addOrUpdateSaveItem(updated, { change_type: "add", object: bbox });
        });
        return updated;
      });
    }

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
          childs: newAnns.filter((ann) => ann.data.entity_ref.id === entity.id),
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

    itemMetas.set({
      featuresList: featureValues || { main: {}, objects: {} },
      item: selectedItem.item,
      type: selectedItem.ui.type,
    });
  };

  const unsubscribeCanSave = canSave.subscribe((value) => (canSaveCurrentItem = value));

  onDestroy(() => {
    unsubscribeCanSave();
  });

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
  const startExpand = (e: MouseEvent) => {
    initialOIAreaX = e.clientX;
    initialOIAreaWidth = objectInspectorAreaMaxWidth;
    window.addEventListener("mousemove", expand, true);
    window.addEventListener("mouseup", stopExpand, true);
  };

  const stopExpand = () => {
    window.removeEventListener("mousemove", expand, true);
    window.removeEventListener("mouseup", stopExpand, true);
  };

  const expand = (e: MouseEvent) => {
    const delta = e.clientX - initialOIAreaX;
    objectInspectorAreaMaxWidth = Math.max(minOIAreaWidth, initialOIAreaWidth - delta);
  };

  const handleKeyDown = (event: KeyboardEvent) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "s") {
      event.preventDefault();
      if ($canSave && !isSaving) {
        void onSave();
      }
    }
  };
</script>

<svelte:window on:keydown={handleKeyDown} />

<div class="w-full h-full flex" role="tab" tabindex="0">
  {#if isSaving}
    <div
      class="h-full w-full flex justify-center items-center absolute top-0 left-0 bg-black/10 z-50"
    >
      <Loader2Icon class="animate-spin" />
    </div>
  {/if}
  <div
    class="flex flex-col w-full overflow-hidden"
    style={`max-width: calc(100%  - ${objectInspectorAreaMaxWidth}px);`}
  >
    {#if showAutogenBBoxAlert}
      <div
        class="bg-warning/10 border-b border-warning/20 px-4 py-2 flex items-center justify-between gap-4 animate-in slide-in-from-top duration-300"
        transition:fade
      >
        <div class="flex items-center gap-3">
          <div class="p-1.5 rounded-full bg-warning/20 text-warning">
            <ShieldAlertIcon size={18} />
          </div>
          <div class="flex flex-col">
            <span class="text-sm font-bold text-warning-foreground">
              Bounding boxes automatically generated
            </span>
            <span class="text-[11px] text-warning-foreground/60 leading-tight">
              Some masks were missing bounding boxes. They have been added for optimal visualization
              and thumbnails.
            </span>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <Button
            variant="outline"
            class="h-8 px-3 border-warning/30 hover:bg-warning/20 text-warning-foreground gap-2 text-xs"
            on:click={() => {
              void onSave();
              showAutogenBBoxAlert = false;
            }}
          >
            <SaveIcon size={14} />
            Save All
          </Button>
          <button
            class="p-1.5 rounded-md hover:bg-card/10 text-warning-foreground/40 hover:text-warning-foreground transition-colors"
            on:click={() => (showAutogenBBoxAlert = false)}
            aria-label="Dismiss"
          >
            <XIcon size={16} />
          </button>
        </div>
      </div>
    {/if}
    <div
      id="datasetItemViewerDiv"
      class="flex-1 w-full overflow-hidden"
      in:fade={{ duration: 300, delay: 100 }}
    >
      <!-- 'resize' prop is used to trigger redraw on value change, value itself is not used, but shouldn't be 0, so we add '+1' -->
      <DatasetItemViewer {selectedItem} {isLoading} resize={objectInspectorAreaMaxWidth + 1} />
    </div>
  </div>
  <button
    class="w-1.5 group relative bg-border hover:bg-primary/30 cursor-col-resize h-full transition-colors"
    on:mousedown={startExpand}
    aria-label="Resize object inspector"
  >
    <div
      class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-1 h-8 rounded-full bg-border group-hover:bg-primary/50 transition-colors"
    ></div>
  </button>
  <div
    class="grow overflow-hidden bg-card"
    style={`width: ${objectInspectorAreaMaxWidth}px`}
    in:fly={{ x: 20, duration: 400, delay: 200, easing: cubicOut }}
  >
    <Inspector on:click={onSave} {isLoading} />
  </div>
  <LoadModelModal />
</div>
