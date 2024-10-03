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
  import type { DisplayControl, Annotation, ObjectThumbnail, SaveItem } from "@pixano/core";

  import {
    canSave,
    saveData,
    annotations,
    entities,
    selectedTool,
    colorScale,
    itemMetas,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import {
    getObjectEntity,
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

  export let annotation: Annotation;

  const entity = getObjectEntity(annotation, $entities);

  let open: boolean = false;
  let showIcons: boolean = false;

  $: features = createFeature(entity);
  $: isEditing = annotation.displayControl?.editing || false;
  $: isVisible = !annotation.displayControl?.hidden;
  $: boxIsVisible =
    annotation.datasetItemType === "image" &&
    annotation.is_bbox &&
    !annotation.displayControl?.hidden;
  $: maskIsVisible =
    annotation.datasetItemType === "image" &&
    annotation.is_mask &&
    !annotation.displayControl?.hidden;
  $: keypointsIsVisible =
    annotation.datasetItemType === "image" &&
    annotation.is_keypoints &&
    !annotation.displayControl?.hidden;

  $: color = $colorScale[1](annotation.id);

  const handleIconClick = (
    displayControlProperty: keyof DisplayControl,
    value: boolean,
    properties: ("bbox" | "mask" | "keypoints")[] = ["bbox", "mask", "keypoints"],
  ) => {
    annotations.update((objects) =>
      objects.map((object) => {
        if (displayControlProperty === "editing") {
          object.highlighted = object.id === annotation.id ? "self" : "none";
          object.highlighted = value ? object.highlighted : "all";
          object.displayControl = {
            ...object.displayControl,
            editing: false,
          };
        }
        if (object.id === annotation.id) {
          object = toggleObjectDisplayControl(object, displayControlProperty, properties, value);
          objectIdBeingEdited.set(value ? object.id : null);
        }
        return object;
      }),
    );
  };

  const deleteObject = () => {
    annotations.update((oldObjects) => oldObjects.filter((object) => object.id !== annotation.id));
    const save_item: SaveItem = {
      change_type: "delete",
      object: annotation,
    };
    //TODO remove entities associated with ?
    //...but here annotation should be entity in fact.
    // So we have to found child annotations/entities of this entity, end delete them too
    saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
    canSave.set(true);
  };

  const saveInputChange = (value: string | boolean | number, propertyName: string) => {
    let changedObj = false;
    annotations.update((oldObjects) =>
      oldObjects.map((object) => {
        if (object.id === annotation.id) {
          object.features = {
            ...object.features,
            [propertyName]: {
              ...object.features[propertyName],
              value,
            },
          };
          const save_item: SaveItem = {
            change_type: "update",
            object,   //TODO should be entity ?
          };
          saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
          changedObj = true;
        }
        return object;
      }),
    );
    if (changedObj) {
      canSave.set(true);
    }
  };

  const onColoredDotClick = () =>
    annotations.update((objects) => highlightCurrentObject(objects, annotation));

  const onEditIconClick = () => {
    handleIconClick("editing", !isEditing), (open = true);
    !isEditing && selectedTool.set(panTool);
  };

  const thumbnail: ObjectThumbnail | null = defineObjectThumbnail($itemMetas, annotation);
</script>

<article
  on:mouseenter={() => (showIcons = true)}
  on:mouseleave={() => (showIcons = open)}
  id={createObjectCardId(annotation)}
>
  <div
    class={cn("flex items-center mt-1  rounded justify-between text-slate-800 bg-white border-2 ")}
    style="border-color:{annotation.highlighted === 'self' ? color : 'transparent'}"
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
      <span class="truncate w-max flex-auto">{annotation.id}</span>
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
          {#if annotation.datasetItemType === "image"}
            <div>
              <p class="font-medium first-letter:uppercase">display</p>
              <div class="flex gap-4">
                {#if annotation.is_bbox}
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
                {#if annotation.is_mask}
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
                {#if annotation.is_keypoints}
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
