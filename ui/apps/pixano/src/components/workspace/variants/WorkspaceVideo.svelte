<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Canvas2D } from "$components/workspace/canvas2d";
  import { Loader2Icon } from "lucide-svelte";
  import { untrack } from "svelte";

  import VideoInspector from "../VideoPlayer/VideoInspector.svelte";
  import { sourcesStore } from "$lib/stores/appStores.svelte";
  import {
    currentFrameIndex,
    currentItemId,
    imagesPerView,
    imagesPerViewBuffer,
    lastFrameIndex,
    videoControls,
    videoViewNames,
  } from "$lib/stores/videoStores.svelte";
  import {
    annotations,
    brushSettings,
    colorScale,
    current_itemBBoxes,
    current_itemKeypoints,
    current_itemMasks,
    entities,
    imageSmoothing,
    itemMasks,
    merges,
    newShape,
    selectedTool,
  } from "$lib/stores/workspaceStores.svelte";
  import { ToolType, type SelectionTool } from "$lib/tools";
  import {
    Annotation,
    BaseSchema,
    BBox,
    DatasetItem,
    Entity,
    Keypoints,
    SequenceFrame,
    ShapeType,
    Track,
    type EditShape,
    type SaveItem,
  } from "$lib/ui";
  import { getPixanoSource, getTopEntity } from "$lib/utils/entityLookupUtils";
  import { updateExistingAnnotation } from "$lib/utils/entityMutations";
  import { highlightEntity, scrollIntoView } from "$lib/utils/highlightOperations";
  import { verticesToCoordsAndStates } from "$lib/utils/keypointsUtils";
  import { saveTo } from "$lib/utils/saveItemUtils";
  import { loadInitialFrames, setBufferSpecs } from "$lib/utils/videoOperations";

  interface Props {
    selectedItem: DatasetItem;
    resize: number;
  }

  interface BrushSettings {
    brushRadius: number;
    lazyRadius: number;
    friction: number;
  }

  let { selectedItem, resize }: Props = $props();

  $effect(() => {
    if (selectedItem) {
      currentFrameIndex.value = 0;
    }
  });

  let inspectorMaxHeight = $state(250);
  let expanding = $state(false);
  let isLoaded = $state(false);
  let loadingCycle = 0;

  const handleCanvasShapeChange = (shape: import("$lib/ui").Shape) => {
    // Draft creation now stays local in Canvas2D and should not trigger store churn.
    if (shape.status === "creating") return;
    newShape.value = shape;
  };

  $effect(() => {
    untrack(() => {
      const cycle = ++loadingCycle;
      const viewNames = Object.keys(selectedItem.views);
      const longestView = Math.max(
        ...Object.values(selectedItem.views).map((view) => (view as SequenceFrame[]).length),
      );

      clearInterval(videoControls.value.intervalId);
      videoControls.update((old) => ({ ...old, intervalId: 0, isLoaded: false }));
      isLoaded = false;

      // Store item ID and view names for batch fetcher
      currentItemId.value = selectedItem.item.id;
      videoViewNames.value = viewNames;

      // Initialize the buffer structure with arrays for each view
      for (const viewKey of viewNames) {
        imagesPerViewBuffer.value[viewKey] = [];
      }

      lastFrameIndex.value = longestView - 1;
      setBufferSpecs();

      // Load first batch, then mount Canvas2D
      void loadInitialFrames()
        .then(() => {
          if (cycle !== loadingCycle) return;
          isLoaded = true;
          videoControls.update((old) => ({ ...old, isLoaded: true }));
        })
        .catch((error) => {
          if (cycle !== loadingCycle) return;
          console.error("Failed to load initial video frames", error);
          isLoaded = false;
          videoControls.update((old) => ({ ...old, isLoaded: false }));
        });
    });
  });

  function mergeFusionRangesByView(to_fuse: Entity[]): Record<string, [number, number][]> {
    //build combined track ranges for each view of to_fuse entities
    const tracksByView: Record<string, Track[]> = {};
    to_fuse
      .flatMap((ent) =>
        ent.ui.childs
          ? (ent.ui.childs.filter((ann) => ann.is_type(BaseSchema.Tracklet)) as Track[])
          : [],
      )
      .forEach((trk) => {
        if (!(trk.data.view_name in tracksByView)) tracksByView[trk.data.view_name] = [];
        tracksByView[trk.data.view_name].push(trk);
      });

    const mergedByView: Record<string, [number, number][]> = {};
    Object.entries(tracksByView).forEach(([view, viewTracks]) => {
      mergedByView[view] = [];
      if (viewTracks.length > 0) {
        // sort to ease merge
        viewTracks.sort((a, b) => a.data.start_frame - b.data.start_frame);
        let currentTrack = { ...viewTracks[0] };
        for (let i = 1; i < viewTracks.length; i++) {
          const trk = viewTracks[i];
          if (trk.data.start_frame <= currentTrack.data.end_frame) {
            // Merge range if overlap (or touching)
            currentTrack.data.end_frame = Math.max(currentTrack.data.end_frame, trk.data.end_frame);
          } else {
            // Add merged range and start a new one
            mergedByView[view].push([currentTrack.data.start_frame, currentTrack.data.end_frame]);
            currentTrack = { ...trk };
          }
        }
        // Add last range
        mergedByView[view].push([currentTrack.data.start_frame, currentTrack.data.end_frame]);
      }
    });
    return mergedByView;
  }

  function canMergeRangesByView(
    record1: Record<string, [number, number][]>,
    record2: Record<string, [number, number][]>,
  ): boolean {
    // Get all possible views
    const allViews = new Set([...Object.keys(record1), ...Object.keys(record2)]);

    for (const view of allViews) {
      const ranges1 = record1[view] || [];
      const ranges2 = record2[view] || [];

      // sort both ranges on start then end
      const allRanges = [...ranges1, ...ranges2].sort((a, b) =>
        a[0] === b[0] ? a[1] - b[1] : a[0] - b[0],
      );
      // check if ranges overlap or touch
      for (let i = 1; i < allRanges.length; i++) {
        const prev = allRanges[i - 1];
        const curr = allRanges[i];
        if (prev[1] >= curr[0]) {
          return false;
        }
      }
    }
    return true;
  }

  const checkMergeForbids = (to_fuse: Entity[]) => {
    const forbids: Entity[] = merges.value.forbids;
    const to_fuse_ranges = mergeFusionRangesByView(to_fuse);
    const others = entities.value.filter(
      (ent) => !to_fuse.includes(ent) && ent.data.parent_id === "",
    );
    others.forEach((ent) => {
      const ranges = mergeFusionRangesByView([ent]);
      if (canMergeRangesByView(ranges, to_fuse_ranges)) {
        //remove from forbids (if present)
        if (forbids.includes(ent)) {
          const remove_index = forbids.indexOf(ent, 0);
          forbids.splice(remove_index, 1);
        }
      } else {
        //add to forbids
        if (!forbids.includes(ent)) {
          forbids.push(ent);
        }
      }
    });
    //adapt highlights
    annotations.update((anns) =>
      anns.map((ann) => {
        const top_ent = getTopEntity(ann);
        if (forbids.map((ent) => ent.id).includes(top_ent.id))
          ann.ui.displayControl.highlighted = "none";
        else if (!to_fuse.map((ent) => ent.id).includes(top_ent.id))
          ann.ui.displayControl.highlighted = "all";
        return ann;
      }),
    );
  };

  const merge = (clicked_ann: Annotation) => {
    if (selectedTool.value.type === ToolType.Fusion) {
      const top_entity = getTopEntity(clicked_ann);
      //check if top_entity is allowed
      if (merges.value.forbids.includes(top_entity)) return;

      if (!merges.value.to_fuse.includes(top_entity)) {
        merges.update((assoc) => ({
          to_fuse: [...assoc.to_fuse, top_entity],
          forbids: assoc.forbids,
        }));
        //highlight
        annotations.update((anns) =>
          anns.map((ann) => {
            if (top_entity.ui.childs?.includes(ann) /*&& !ann.is_type(BaseSchema.Tracklet)*/) {
              ann.ui.displayControl.highlighted = "self";
            }
            return ann;
          }),
        );
      } else {
        //already here, then remove it
        merges.update((assoc) => {
          const remove_index = assoc.to_fuse.indexOf(top_entity, 0);
          assoc.to_fuse.splice(remove_index, 1);
          return assoc;
        });
        //unhighlight
        annotations.update((anns) =>
          anns.map((ann) => {
            if (top_entity.ui.childs?.includes(ann) /*&& !ann.is_type(BaseSchema.Tracklet)*/) {
              ann.ui.displayControl.highlighted = "all";
            }
            return ann;
          }),
        );
      }
      checkMergeForbids(merges.value.to_fuse);
    }
  };

  const editKeyItemInTracklet = (
    annotations: Annotation[],
    shape: EditShape,
    currentFrame: number,
  ): { objects: Annotation[]; save_data: SaveItem } => {
    let saveData: SaveItem;
    let updated_annotations: Annotation[];
    //find corresponding annotation
    const update_ann = annotations.find((ann) => ann.id === shape.shapeId);
    if (update_ann) {
      if (update_ann.is_type(BaseSchema.BBox) && shape.type === ShapeType.bbox) {
        (update_ann as BBox).data.coords = shape.coords;
      } else if (update_ann.is_type(BaseSchema.Keypoints) && shape.type === ShapeType.keypoints) {
        const { coords, states } = verticesToCoordsAndStates(shape.vertices);
        (update_ann as Keypoints).data.coords = coords;
        (update_ann as Keypoints).data.states = states;
      } else if (update_ann.is_type(BaseSchema.Mask)) {
        // mask not implemented yet in video
      } else {
        // should not happen
        console.error(
          `ERROR: mismatching types ${shape.type} & ${update_ann.table_info.base_schema}`,
        );
      }
      const pixSource = getPixanoSource(sourcesStore);
      update_ann.data.source_id = pixSource.id;
      //update
      updated_annotations = annotations.map((ann) => (ann.id === update_ann.id ? update_ann : ann));
      saveData = {
        change_type: "update",
        data: update_ann,
      };
    } else {
      //updated an interpolated annotation: create it
      //use start ann of interpolated as base for new ann
      let newAnn: Annotation | undefined = undefined;
      if (shape.type === ShapeType.bbox) {
        const interpolated_box = current_itemBBoxes.value.find((box) => box.id === shape.shapeId);
        if (interpolated_box && "startRef" in interpolated_box) {
          const newBBox = structuredClone(interpolated_box.startRef as BBox);
          newBBox.id = shape.shapeId;
          newBBox.data.coords = shape.coords;
          newBBox.data.view_name = shape.viewRef.name;
          newBBox.data.frame_id = shape.viewRef.id;
          newBBox.ui.frame_index = currentFrame;
          newBBox.updated_at = new Date(Date.now()).toISOString().replace(/Z$/, "+00:00");
          newAnn = newBBox;
        }
      } else if (shape.type === ShapeType.keypoints) {
        const interpolated_kpt = current_itemKeypoints.value.find(
          (kpt) => kpt.id === shape.shapeId,
        );
        if (interpolated_kpt && "startRef" in interpolated_kpt) {
          const keypointRef = annotations.find(
            (ann) =>
              ann.is_type(BaseSchema.Keypoints) && ann.id === interpolated_kpt.ui.startRef?.id,
          ) as Keypoints;
          if (keypointRef) {
            const newKpt = structuredClone(keypointRef);
            const { coords, states } = verticesToCoordsAndStates(shape.vertices);
            newKpt.id = shape.shapeId;
            newKpt.data.coords = coords;
            newKpt.data.states = states;
            newKpt.data.view_name = shape.viewRef.name;
            newKpt.data.frame_id = shape.viewRef.id;
            newKpt.ui.frame_index = currentFrame;
            newKpt.updated_at = new Date(Date.now()).toISOString().replace(/Z$/, "+00:00");
            newAnn = newKpt;
          }
        }
      } else if (shape.type === ShapeType.mask || shape.type === ShapeType.polygon) {
        // mask not implemented yet in video
      }
      if (!newAnn) {
        //TODO - remove this when mask managed (used mainly to avoid lint warnings)
        throw new Error("Masks are not managed yet in video!");
      }
      //update
      const pixSource = getPixanoSource(sourcesStore);
      newAnn.data.source_id = pixSource.id;
      updated_annotations = [...annotations, newAnn];
      saveData = {
        change_type: "add",
        data: newAnn,
      };
    }
    return {
      objects: updated_annotations,
      save_data: saveData,
    };
  };

  const updateOrCreateShape = (shape: EditShape) => {
    const isSelectionOnlyHighlight =
      shape.status === "editing" && shape.type === ShapeType.none && shape.highlighted === "self";

    if (isSelectionOnlyHighlight) {
      let targetEntityId = shape.top_entity_id ?? "";
      if (!targetEntityId && shape.shapeId) {
        const selectedAnnotation = annotations.value.find((ann) => ann.id === shape.shapeId);
        if (selectedAnnotation) {
          targetEntityId = getTopEntity(selectedAnnotation).id;
        }
      }
      if (targetEntityId) {
        highlightEntity(targetEntityId, false);
      }
      newShape.value = { status: "none" };
      return;
    }

    if (shape.type === ShapeType.bbox || shape.type === ShapeType.keypoints) {
      let { objects, save_data } = editKeyItemInTracklet(
        annotations.value,
        shape,
        currentFrameIndex.value,
      );
      annotations.value = objects;
      if (save_data) saveTo(save_data.change_type, save_data.data);
    } else {
      annotations.update((objects) => updateExistingAnnotation(objects, shape));
    }
    newShape.value = { status: "none" };
  };

  $effect(() => {
    const shape = newShape.value;
    const toolType = selectedTool.value.type;
    if (shape.status === "editing") {
      untrack(() => {
        if (toolType !== ToolType.Fusion) {
          updateOrCreateShape(shape);
        } else {
          if (shape.top_entity_id) {
            scrollIntoView(shape.top_entity_id);
          }
        }
      });
    }
  });

  const expand = (e: MouseEvent) => {
    if (expanding) {
      inspectorMaxHeight = document.body.scrollHeight - e.pageY;
    }
  };
</script>

<section
  class="h-full w-full flex flex-col"
  onmouseup={() => {
    expanding = false;
  }}
  onmousemove={expand}
  role="tab"
  tabindex="0"
>
  <div class="overflow-hidden grow relative">
    {#if isLoaded && current_itemBBoxes.value && current_itemKeypoints.value && itemMasks.value}
      <Canvas2D
        selectedItemId={selectedItem.item.id}
        imagesPerView={imagesPerView.value}
        colorScale={colorScale.value[1]}
        bboxes={current_itemBBoxes.value}
        masks={current_itemMasks.value}
        keypoints={current_itemKeypoints.value}
        canvasSize={inspectorMaxHeight + resize}
        isVideo={true}
        isPlaybackActive={videoControls.value.intervalId !== 0}
        imageSmoothing={imageSmoothing.value}
        selectedTool={selectedTool.value}
        brushSettings={brushSettings.value}
        newShape={newShape.value}
        onSelectedToolChange={(tool: SelectionTool) => {
          selectedTool.value = tool;
        }}
        onNewShapeChange={(shape) => {
          handleCanvasShapeChange(shape as import("$lib/ui").Shape);
        }}
        onBrushSettingsChange={(settings: BrushSettings) => {
          brushSettings.value = settings;
        }}
        {merge}
      />
    {:else}
      <div class="h-full w-full bg-canvas flex items-center justify-center">
        <div class="flex flex-col items-center gap-3 text-muted-foreground">
          <Loader2Icon class="h-8 w-8 animate-spin text-white" />
          <p class="text-sm">Loading video frames...</p>
        </div>
      </div>
    {/if}
  </div>
  {#if isLoaded && current_itemBBoxes.value && current_itemKeypoints.value && itemMasks.value}
    <button
      type="button"
      aria-label="Resize canvas and inspector panels"
      class="h-1 bg-primary-light cursor-row-resize w-full"
      onmousedown={() => {
        expanding = true;
      }}
    ></button>
    <div
      class="h-full grow max-h-[25%] overflow-hidden"
      style={`max-height: ${inspectorMaxHeight}px`}
    >
      <VideoInspector bboxes={current_itemBBoxes.value} keypoints={current_itemKeypoints.value} />
    </div>
  {/if}
</section>
