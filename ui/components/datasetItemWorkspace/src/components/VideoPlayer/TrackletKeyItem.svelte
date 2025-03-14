<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import type { SaveItem, TrackletItem } from "@pixano/core";
  import { BaseSchema, cn, ContextMenu, Tracklet } from "@pixano/core";

  import { sourcesStore } from "../../../../../apps/pixano/src/lib/stores/datasetStores";
  import { addOrUpdateSaveItem, getPixanoSource } from "../../lib/api/objectsApi";
  import { annotations, entities, saveData } from "../../lib/stores/datasetItemWorkspaceStores";
  import { currentFrameIndex, lastFrameIndex } from "../../lib/stores/videoViewerStores";

  export let trackId: string;

  export let itemFrameIndex: number;
  export let tracklet: Tracklet;
  export let color: string;
  export let height: number;
  export let top: number;
  export let oneFrameInPixel: number;
  export let onEditKeyItemClick: (frameIndex: TrackletItem["frame_index"]) => void;
  export let onClick: (button: number, clientX: number) => void;
  export let updateTrackletWidth: (
    newIndex: TrackletItem["frame_index"],
    draggedIndex: TrackletItem["frame_index"],
  ) => void;
  export let canContinueDragging: (
    newIndex: TrackletItem["frame_index"],
    draggedIndex: TrackletItem["frame_index"],
  ) => boolean;
  export let resetTool: () => void;

  let isItemBeingEdited = false;

  $: {
    const currentObjectBeingEdited = $annotations.find(
      (object) => object.ui.displayControl?.editing,
    );
    isItemBeingEdited =
      itemFrameIndex === $currentFrameIndex && currentObjectBeingEdited?.id === trackId;
  }

  const onDeleteItemClick = () => {
    const ann_to_del = tracklet.ui.childs.find((ann) => ann.ui.frame_index === itemFrameIndex);
    if (!ann_to_del) return;
    if (tracklet.ui.childs.length <= 2) {
      console.error("Deleting one of 2 last item of tracklet, it should not happen.");
      return;
    }
    let changed_tracklet = false;
    annotations.update((anns) =>
      anns
        .map((ann) => {
          if (ann.id === tracklet.id && ann.is_type(BaseSchema.Tracklet)) {
            (ann as Tracklet).ui.childs = (ann as Tracklet).ui.childs.filter(
              (fann) => fann.ui.frame_index !== itemFrameIndex,
            );
            //if ann_to_del first/last of tracklet, need to "resize" (childs should be sorted)
            if (itemFrameIndex === tracklet.data.start_timestep) {
              (ann as Tracklet).data.start_timestep = (
                ann as Tracklet
              ).ui.childs[0].ui.frame_index!;
              changed_tracklet = true;
            }
            if (itemFrameIndex === tracklet.data.end_timestep) {
              (ann as Tracklet).data.end_timestep = (ann as Tracklet).ui.childs[
                (ann as Tracklet).ui.childs.length - 1
              ].ui.frame_index!;
              changed_tracklet = true;
            }
          }
          return ann;
        })
        .filter((ann) => ann.id !== ann_to_del.id),
    );
    entities.update((ents) =>
      ents.map((ent) => {
        if (ent.is_track && ent.id === tracklet.data.entity_ref.id) {
          ent.ui.childs = ent.ui.childs?.filter((ann) => ann.id !== ann_to_del.id);
        }
        return ent;
      }),
    );

    const save_del_ann: SaveItem = {
      change_type: "delete",
      object: ann_to_del,
    };
    saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_del_ann));
    if (changed_tracklet) {
      const pixSource = getPixanoSource(sourcesStore);
      tracklet.data.source_ref = { id: pixSource.id, name: pixSource.table_info.name };
      const save_upd_tracklet: SaveItem = {
        change_type: "update",
        object: tracklet,
      };
      saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_upd_tracklet));
    }
  };

  export const getKeyItemLeftPosition = (frameIndex: number) => {
    const itemFrameIndex = frameIndex > $lastFrameIndex ? $lastFrameIndex : frameIndex;
    const leftPosition = (itemFrameIndex / ($lastFrameIndex + 1)) * 100;
    return leftPosition;
  };

  let left = getKeyItemLeftPosition(itemFrameIndex);

  const dragMe = (node: HTMLButtonElement) => {
    if (
      tracklet.ui.childs[0].ui.frame_index !== itemFrameIndex &&
      tracklet.ui.childs[tracklet.ui.childs.length - 1].ui.frame_index !== itemFrameIndex
    )
      return;

    let moving = false;
    let startPosition: number;
    let startFrameIndex: number;
    let startOneFrameInPixel: number;
    let newFrameIndex: number | undefined;

    node.addEventListener("mousedown", (event) => {
      moving = true;
      startPosition = event.clientX;
      startFrameIndex = itemFrameIndex;
      startOneFrameInPixel = oneFrameInPixel;
      resetTool();
      const dragController = new AbortController();

      window.addEventListener(
        "mousemove",
        (event) => {
          if (moving) {
            const distance = event.clientX - startPosition;
            const raise = distance / startOneFrameInPixel;
            newFrameIndex = Math.round(startFrameIndex + raise);
            if (newFrameIndex < 0 || newFrameIndex > $lastFrameIndex) return;
            const canContinue = canContinueDragging(newFrameIndex, itemFrameIndex);
            if (canContinue) {
              left = getKeyItemLeftPosition(newFrameIndex);
            }
          }
        },
        { signal: dragController.signal },
      );

      window.addEventListener(
        "mouseup",
        () => {
          moving = false;
          if (newFrameIndex !== undefined) {
            if (newFrameIndex < 0) newFrameIndex = 0;
            if (newFrameIndex > $lastFrameIndex) newFrameIndex = $lastFrameIndex;
            updateTrackletWidth(newFrameIndex, itemFrameIndex);
          }
          newFrameIndex = undefined;
          dragController.abort();
        },
        { signal: dragController.signal },
      );
    });
  };
</script>

<ContextMenu.Root>
  <ContextMenu.Trigger
    class={cn(
      "w-2 z-50 block border-2 border-slate-500 rounded-full absolute left-[-0.5rem] translate-x-[-50%]",
      "hover:scale-150",
      { "bg-primary !border-primary": isItemBeingEdited },
    )}
    style={`left: ${left}%; top: ${top + height * 0.125}%; height: ${height * 0.75}%; background-color: ${color}`}
  >
    <button
      class="w-full h-full rounded-full absolute"
      style={`background-color: ${color}`}
      use:dragMe
      on:click={(e) => onClick(e.button, e.clientX)}
    />
  </ContextMenu.Trigger>
  <ContextMenu.Content>
    {#if tracklet.ui.childs?.length > 2}
      <ContextMenu.Item on:click={() => onDeleteItemClick()}>Remove item</ContextMenu.Item>
    {/if}
    {#if !isItemBeingEdited}
      <ContextMenu.Item on:click={() => onEditKeyItemClick(itemFrameIndex)}>
        Edit item
      </ContextMenu.Item>
    {/if}
  </ContextMenu.Content>
</ContextMenu.Root>
