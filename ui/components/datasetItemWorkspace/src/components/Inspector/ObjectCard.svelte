<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Eye, EyeOff, Trash2, Pencil, ChevronRight } from "lucide-svelte";

  import { cn, IconButton, Checkbox } from "@pixano/core/src";
  import { Thumbnail } from "@pixano/canvas2d";
  import type { DisplayControl, ItemObject, ObjectThumbnail, SaveItem } from "@pixano/core";

  import {
    canSave,
    saveData,
    itemObjects,
    selectedTool,
    colorScale,
    itemMetas,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import {
    createObjectCardId,
    toggleObjectDisplayControl,
    highlightCurrentObject,
    defineObjectThumbnail,
  } from "../../lib/api/objectsApi";
  import { createFeature } from "../../lib/api/featuresApi";
  import { addOrUpdateSaveItem } from "../../lib/api/objectsApi";

  import UpdateFeatureInputs from "../Features/UpdateFeatureInputs.svelte";
  import { panTool } from "../../lib/settings/selectionTools";
  import { objectIdBeingEdited } from "../../lib/stores/videoViewerStores";
  import { Item } from "@pixano/core/src/components/ui/command";

  export let itemObject: ItemObject;

  let open: boolean = false;
  let showIcons: boolean = false;

  $: features = createFeature(itemObject.features);
  $: isEditing = itemObject.displayControl?.editing || false;
  $: isVisible = !itemObject.displayControl?.hidden;
  $: boxIsVisible =
    itemObject.datasetItemType === "image" && !itemObject.bbox?.displayControl?.hidden;
  $: maskIsVisible =
    itemObject.datasetItemType === "image" && !itemObject.mask?.displayControl?.hidden;
  $: keypointsIsVisible =
    itemObject.datasetItemType === "image" && !itemObject.keypoints?.displayControl?.hidden;

  $: color = $colorScale[1](itemObject.id);

  const handleIconClick = (
    displayControlProperty: keyof DisplayControl,
    value: boolean,
    properties: ("bbox" | "mask" | "keypoints")[] = ["bbox", "mask", "keypoints"],
  ) => {
    itemObjects.update((objects) =>
      objects.map((object) => {
        if (displayControlProperty === "editing") {
          object.highlighted = object.id === itemObject.id ? "self" : "none";
          object.highlighted = value ? object.highlighted : "all";
          object.displayControl = {
            ...object.displayControl,
            editing: false,
          };
        }
        if (object.id === itemObject.id) {
          object = toggleObjectDisplayControl(object, displayControlProperty, properties, value);
          objectIdBeingEdited.set(value ? object.id : null);
        }
        return object;
      }),
    );
  };

  const deleteObject = () => {
    itemObjects.update((oldObjects) => oldObjects.filter((object) => object.id !== itemObject.id));
    let del_ids: Record<string, string[]> = {};
    if (itemObject.datasetItemType === "video") {
      if (itemObject.keypoints) {
        del_ids["keypoints"] = itemObject.keypoints.map((kpt) => kpt.id);
      }
      if (itemObject.boxes) {
        del_ids["bbox"] = itemObject.boxes.map((box) => box.id);
      }
      del_ids["tracklet"] = itemObject.track.map((tracklet) => tracklet.id);
      del_ids["top_entity"] = [itemObject.id];
    } else {
      if (itemObject.keypoints) {
        del_ids["keypoints"] = [itemObject.keypoints.id];
      }
      if (itemObject.bbox) {
        del_ids["bbox"] = [itemObject.bbox.id];
      }
      if (itemObject.mask) {
        del_ids["mask"] = [itemObject.mask.id];
      }
      del_ids["top_entity"] = [itemObject.id];
    }
    const save_item: SaveItem = {
      change_type: "delete",
      ref_name: "", //don't need
      is_video: itemObject.datasetItemType === "video",
      data: del_ids,
    };
    saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
    canSave.set(true);
  };

  const saveInputChange = (value: string | boolean | number, propertyName: string) => {
    let changedObj = false;
    itemObjects.update((oldObjects) =>
      oldObjects.map((object) => {
        if (object.id === itemObject.id) {
          object.features = {
            ...object.features,
            [propertyName]: {
              ...object.features[propertyName],
              value,
            },
          };
          const save_item: SaveItem = {
            change_type: "add_or_update",
            ref_name: "top_entity",
            is_video: itemObject.datasetItemType === "video",
            data: {
              id: object.id,
              item_id: object.item_id,
              source_id: object.source_id,
              features: object.features,
              ref_name: "top_entity",
              entity_ref: { id: "", name: "" },
            },
          };
          saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
        }
        return object;
      }),
    );
    if (changedObj) {
      canSave.set(true);
    }
  };

  const onColoredDotClick = () =>
    itemObjects.update((objects) => highlightCurrentObject(objects, itemObject));

  const onEditIconClick = () => {
    handleIconClick("editing", !isEditing), (open = true);
    !isEditing && selectedTool.set(panTool);
  };

  const thumbnail: ObjectThumbnail | null = defineObjectThumbnail($itemMetas, itemObject);
</script>

<article
  on:mouseenter={() => (showIcons = true)}
  on:mouseleave={() => (showIcons = open)}
  id={createObjectCardId(itemObject)}
>
  <div
    class={cn("flex items-center mt-1  rounded justify-between text-slate-800 bg-white border-2 ")}
    style="border-color:{itemObject.highlighted === 'self' ? color : 'transparent'}"
  >
    <div class="flex items-center flex-auto max-w-[50%]">
      <IconButton
        on:click={() => handleIconClick("hidden", isVisible)}
        tooltipContent={isVisible ? "Hide object" : "Show object"}
      >
        {#if isVisible}
          <Eye class="h-4" />
        {:else}
          <EyeOff class="h-4" />
        {/if}
      </IconButton>
      <button
        class="rounded-full border w-3 h-3 mr-2 flex-[0_0_0.75rem]"
        style="background:{color}"
        title="Highlight object"
        on:click={onColoredDotClick}
      />
      <span class="truncate w-max flex-auto">{itemObject.id}</span>
    </div>
    <div class="flex items-center">
      {#if showIcons || isEditing}
        <IconButton tooltipContent="Edit object" selected={isEditing} on:click={onEditIconClick}
          ><Pencil class="h-4" /></IconButton
        >
        <IconButton tooltipContent="Delete object" on:click={deleteObject}
          ><Trash2 class="h-4" /></IconButton
        >
      {/if}
      <IconButton
        on:click={() => (open = !open)}
        tooltipContent={open ? "Hide features" : "Show features"}
      >
        <ChevronRight class={cn("transition", { "rotate-90": open })} strokeWidth={1} />
      </IconButton>
    </div>
  </div>
  {#if open}
    <div class="pl-5 border-b border-b-slate-600 text-slate-800 bg-white">
      <div
        class="border-l-4 border-dashed border-red-400 pl-4 pb-4 pt-4 flex flex-col gap-4"
        style="border-color:{color}"
      >
        <div class="flex flex-col gap-2">
          {#if itemObject.datasetItemType === "image"}
            <div>
              <p class="font-medium first-letter:uppercase">display</p>
              <div class="flex gap-4">
                {#if itemObject.bbox}
                  <div class="flex gap-2 mt-2 items-center">
                    <p class="font-light first-letter:uppercase">Box</p>
                    <Checkbox
                      handleClick={() => handleIconClick("hidden", boxIsVisible, ["bbox"])}
                      bind:checked={boxIsVisible}
                      title={boxIsVisible ? "Hide" : "Show"}
                      class="mx-1"
                    />
                  </div>
                {/if}
                {#if itemObject.mask}
                  <div class="flex gap-2 mt-2 items-center">
                    <p class="font-light first-letter:uppercase">Mask</p>
                    <Checkbox
                      handleClick={() => handleIconClick("hidden", maskIsVisible, ["mask"])}
                      bind:checked={maskIsVisible}
                      title={maskIsVisible ? "Hide" : "Show"}
                      class="mx-1"
                    />
                  </div>
                {/if}
                {#if itemObject.keypoints}
                  <div class="flex gap-2 mt-2 items-center">
                    <p class="font-light first-letter:uppercase">Key points</p>
                    <Checkbox
                      handleClick={() =>
                        handleIconClick("hidden", keypointsIsVisible, ["keypoints"])}
                      bind:checked={keypointsIsVisible}
                      title={keypointsIsVisible ? "Hide" : "Show"}
                      class="mx-1"
                    />
                  </div>
                {/if}
              </div>
            </div>
          {/if}
          <UpdateFeatureInputs featureClass="objects" {features} {isEditing} {saveInputChange} />
          {#if thumbnail}
            <Thumbnail
              imageDimension={thumbnail.baseImageDimensions}
              coords={thumbnail.coords}
              imageUrl={`/${thumbnail.uri}`}
              minWidth={150}
              maxWidth={300}
            />
          {/if}
        </div>
      </div>
    </div>
  {/if}
</article>
