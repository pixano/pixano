<script lang="ts">
  /**
   * @copyright CEA
   * @author CEA
   * @license CECILL
   *
   * This software is a collaborative computer program whose purpose is to
   * generate and explore labeled data for computer vision applications.
   * This software is governed by the CeCILL-C license under French law and
   * abiding by the rules of distribution of free software. You can use,
   * modify and/ or redistribute the software under the terms of the CeCILL-C
   * license as circulated by CEA, CNRS and INRIA at the following URL
   *
   * http://www.cecill.info
   */

  import { ContextMenu, type BBoxCoordinates, type ItemObject } from "@pixano/core";
  import { newShape, itemObjects } from "../../lib/stores/datasetItemWorkspaceStores";
  import { inflexionPointBeingEdited } from "../../lib/stores/videoViewerStores";

  export let videoSpeed: number;
  export let zoomLevel: number[];
  export let object: ItemObject;
  export let videoTotalLengthInMs: number;
  export let lastImageIndex: number;
  export let onPlayerClick: (event: MouseEvent) => void;

  const onContextMenu = (event: MouseEvent) => {
    newShape.set({
      status: "editing",
      type: "none",
      shapeId: object.id,
      highlighted: "self",
    });
    onPlayerClick(event);
  };

  const firstBoxStartIndex = object.bbox?.coordinates?.[0]?.startIndex || 1;
  let startPosition = ((firstBoxStartIndex * videoSpeed) / videoTotalLengthInMs) * 100;

  const lastBoxEndIndex = object.bbox?.coordinates?.at(-1)?.endIndex || 1;
  let width =
    (((lastBoxEndIndex > lastImageIndex ? lastImageIndex : lastBoxEndIndex - firstBoxStartIndex) *
      videoSpeed) /
      videoTotalLengthInMs) *
    100;

  const inflexionCoordinates = object.bbox?.coordinates?.filter((c) => c.startIndex !== 0) || [];

  const onEditPointClick = (inflexionPoint: BBoxCoordinates) => {
    inflexionPointBeingEdited.set(inflexionPoint);
    console.log({ inflexionPoint });
    itemObjects.update((objects) =>
      objects.map((o) => {
        if (o.id === object.id) {
          o.displayControl = {
            ...o.displayControl,
            editing: true,
          };
        }
        return o;
      }),
    );
  };
</script>

<div class="border-b border-slate-200 h-12 p-2 pl-0 w-full grid grid-cols-[25%_1fr]">
  <p class="sticky left-0 z-10 bg-white pl-2">{object.id}</p>
  <div class="w-full flex gap-5 relative" style={`width: ${zoomLevel[0]}%`}>
    <ContextMenu.Root>
      <ContextMenu.Trigger
        class="h-full w-full bg-emerald-500 absolute"
        style={`left: ${startPosition}% ; width: ${width}%`}
      >
        <p on:contextmenu|preventDefault={(e) => onContextMenu(e)} class="h-full w-full" />
      </ContextMenu.Trigger>
      <ContextMenu.Content>
        <ContextMenu.Item inset>Add a point</ContextMenu.Item>
        <ContextMenu.Item inset>Remove point</ContextMenu.Item>
        <ContextMenu.Item inset on:click={() => console.log("edit")}>Edit point</ContextMenu.Item>
      </ContextMenu.Content>
    </ContextMenu.Root>
    {#each inflexionCoordinates as inflexionPoint}
      <ContextMenu.Root>
        <ContextMenu.Trigger
          class="w-4 h-4 block bg-indigo-500 rounded-full absolute left-[-0.5rem] top-1/2 translate-y-[-50%]"
          style={`left: ${((inflexionPoint.startIndex * videoSpeed) / videoTotalLengthInMs) * 100}%`}
        />
        <ContextMenu.Content>
          <ContextMenu.Item inset>Remove point</ContextMenu.Item>
          <ContextMenu.Item inset on:click={() => onEditPointClick(inflexionPoint)}
            >Edit point</ContextMenu.Item
          >
        </ContextMenu.Content>
      </ContextMenu.Root>
    {/each}
  </div>
</div>
