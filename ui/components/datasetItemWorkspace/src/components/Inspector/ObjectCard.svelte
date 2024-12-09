<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { derived } from "svelte/store";
  import { Eye, EyeOff, Trash2, Pencil, ChevronRight } from "lucide-svelte";

  import { cn, IconButton, Checkbox } from "@pixano/core/src";
  import { Thumbnail } from "@pixano/canvas2d";
  import {
    type DisplayControl,
    Annotation,
    Entity,
    Item,
    type ObjectThumbnail,
    type SaveItem,
  } from "@pixano/core";

  import {
    saveData,
    annotations,
    entities,
    views,
    selectedTool,
    colorScale,
    itemMetas,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import { currentFrameIndex } from "../../lib/stores/videoViewerStores";
  import {
    getTopEntity,
    createObjectCardId,
    toggleObjectDisplayControl,
    defineObjectThumbnail,
  } from "../../lib/api/objectsApi";
  import { createFeature } from "../../lib/api/featuresApi";
  import type { Feature } from "../../lib/types/datasetItemWorkspaceTypes";

  import { addOrUpdateSaveItem } from "../../lib/api/objectsApi";

  import UpdateFeatureInputs from "../Features/UpdateFeatureInputs.svelte";
  import { panTool } from "../../lib/settings/selectionTools";
  import { datasetSchema } from "../../../../../apps/pixano/src/lib/stores/datasetStores";

  export let entity: Entity;

  let open: boolean = false;
  let showIcons: boolean = false;
  let isHighlighted: boolean = false;
  let isEditing: boolean = false;
  let isVisible: boolean = true;
  let boxIsVisible: boolean = true;
  let maskIsVisible: boolean = true;
  let keypointsIsVisible: boolean = true;

  $: displayName =
    (entity.data.name
      ? (entity.data.name as string) + " "
      : entity.data.category
        ? (entity.data.category as string) + " "
        : "") +
    "(" +
    entity.id +
    ")";

  $: color = $colorScale[1](entity.id);

  $: if (isEditing) open = true;

  const features = derived(
    [currentFrameIndex, entities, annotations],
    ([$currentFrameIndex, $entities, $annotations]) => {
      //features may depends on an annotation change, but we access them with entity.ui.childs instead of $annotations
      //to prevent lint unused-vars
      $annotations;
      //get all features from Top entity (obj) to evental sub entities and annotations
      //let anns_features: Record<string, Feature[]> = {};
      let feats: Record<string, Feature[]> = {};
      let child_anns: Annotation[] = [];
      if ($currentFrameIndex !== null) {
        child_anns = entity.ui.childs!.filter(
          (ann) => !ann.is_tracklet && ann.ui.frame_index! === $currentFrameIndex,
        );
      } else {
        child_anns = entity.ui.childs!.filter((ann) => !ann.is_tracklet);
      }
      for (const ann of child_anns) {
        if (ann.data.entity_ref.id !== entity.id && !(ann.data.entity_ref.id in feats)) {
          //there is a subentity, find it
          const subentity = $entities.find((ent) => ent.id === ann.data.entity_ref.id);
          if (subentity) {
            feats[subentity.id] = createFeature(
              subentity,
              $datasetSchema,
              subentity.table_info.name,
            );
          }
        }
        feats[ann.id] = createFeature(
          ann,
          $datasetSchema,
          ann.table_info.name + "." + ann.data.view_ref.name,
        );
      }
      feats[entity.id] = createFeature(entity, $datasetSchema);

      return Object.values(feats).flat();
    },
  );

  annotations.subscribe(() => {
    isHighlighted = entity.ui.childs?.some((ann) => ann.ui.highlighted === "self") || false;
    isEditing = entity.ui.childs?.some((ann) => ann.ui.displayControl?.editing) || false;
    isVisible = entity.ui.childs?.some((ann) => !ann.ui.displayControl?.hidden) || false;
    boxIsVisible =
      entity.ui.childs?.some(
        (ann) =>
          ann.ui.datasetItemType === "image" && ann.is_bbox && !ann.ui.displayControl?.hidden,
      ) || false;
    maskIsVisible =
      entity.ui.childs?.some(
        (ann) =>
          ann.ui.datasetItemType === "image" && ann.is_mask && !ann.ui.displayControl?.hidden,
      ) || false;
    keypointsIsVisible =
      entity.ui.childs?.some(
        (ann) =>
          ann.ui.datasetItemType === "image" && ann.is_keypoints && !ann.ui.displayControl?.hidden,
      ) || false;
  });

  const handleIconClick = (
    displayControlProperty: keyof DisplayControl,
    value: boolean,
    kind: string | null = null,
  ) => {
    annotations.update((anns) =>
      anns.map((ann) => {
        if (displayControlProperty === "editing") {
          //no change on non current anns for video
          if (ann.ui.datasetItemType === "video") {
            if (ann.ui.frame_index !== $currentFrameIndex) return ann;
          }
          ann.ui.highlighted = getTopEntity(ann, $entities).id === entity.id ? "self" : "none";
          ann.ui.highlighted = value ? ann.ui.highlighted : "all";
          ann.ui.displayControl = {
            ...ann.ui.displayControl,
            editing: false,
          };
        }
        if (
          getTopEntity(ann, $entities).id === entity.id &&
          (!kind || (kind && ann.table_info.base_schema === kind))
        )
          ann = toggleObjectDisplayControl(ann, displayControlProperty, value);
        return ann;
      }),
    );
  };

  const deleteObject = () => {
    const save_item: SaveItem = {
      change_type: "delete",
      object: entity,
    };
    saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
    //delete eventual sub entities
    const subentities = $entities.filter((ent) => ent.data.parent_ref.id === entity.id);
    for (const subent of subentities) {
      const save_item: SaveItem = {
        change_type: "delete",
        object: subent,
      };
      saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
    }
    for (const ann of entity.ui.childs || []) {
      const save_item: SaveItem = {
        change_type: "delete",
        object: ann,
      };
      saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
    }
    const subent_ids = subentities.map((subent) => subent.id);
    annotations.update((oldObjects) =>
      oldObjects.filter((ann) => ![entity.id, ...subent_ids].includes(ann.data.entity_ref.id)),
    );
    entities.update((oldObjects) =>
      oldObjects.filter((ent) => ent.id !== entity.id && ent.data.parent_ref.id !== entity.id),
    );
  };

  const saveInputChange = (
    value: string | boolean | number,
    propertyName: string,
    obj: Item | Entity | Annotation,
  ) => {
    if (["Track", "Entity"].includes(obj.table_info.base_schema)) {
      entities.update((oldObjects) =>
        oldObjects.map((object) => {
          if (object === obj) {
            object.data = {
              ...object.data,
              [propertyName]: value,
            };
            const save_item: SaveItem = {
              change_type: "update",
              object,
            };
            saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
          }
          return object;
        }),
      );
    } else if (obj.table_info.base_schema === "Item") {
      console.warn("This should never happen, we don't have 'item' features in Objects Inspector.");
    } else {
      //Annotation
      annotations.update((oldObjects) =>
        oldObjects.map((object) => {
          if (object === obj) {
            object.data = {
              ...object.data,
              [propertyName]: value,
            };
            const save_item: SaveItem = {
              change_type: "update",
              object,
            };
            saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
          }
          return object;
        }),
      );
    }
  };

  const onColoredDotClick = () => {
    annotations.update((objects) =>
      objects.map((ann) => {
        ann.ui.highlighted = isHighlighted
          ? "all"
          : getTopEntity(ann, $entities).id === entity.id
            ? "self"
            : "none";
        return ann;
      }),
    );
  };

  const onEditIconClick = () => {
    handleIconClick("editing", !isEditing);
    !isEditing && selectedTool.set(panTool);
  };

  const thumb_box: Annotation | undefined = entity.ui.childs?.find((ann) => ann.is_bbox);
  const thumbnail: ObjectThumbnail | null = thumb_box
    ? defineObjectThumbnail($itemMetas, $views, thumb_box)
    : null;
</script>

<article
  on:mouseenter={() => (showIcons = true)}
  on:mouseleave={() => (showIcons = open)}
  id={createObjectCardId(entity)}
>
  <div
    class={cn(
      "flex items-center mt-1 rounded justify-between text-slate-800 bg-white border-2 overflow-hidden",
    )}
    style="border-color:{isHighlighted ? color : 'transparent'}"
  >
    <div class="flex-[1_1_auto] flex items-center overflow-hidden min-w-0">
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
      <span class="truncate flex-auto overflow-hidden overflow-ellipsis whitespace-nowrap"
        >{displayName}</span
      >
    </div>
    <div
      class={cn(
        "flex-shrink-0 flex items-center justify-end",
        showIcons || isEditing ? "basis-[120px]" : "basis-[40px]",
      )}
      style="min-width: 40px;"
    >
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
          {#if entity.ui.childs?.some((ann) => ann.ui.datasetItemType === "image")}
            <div>
              <p class="font-medium first-letter:uppercase">display</p>
              <div class="flex gap-4">
                {#if entity.ui.childs?.some((ann) => ann.is_bbox)}
                  <div class="flex gap-2 mt-2 items-center">
                    <p class="font-light first-letter:uppercase">Box</p>
                    <Checkbox
                      handleClick={() => handleIconClick("hidden", boxIsVisible, "BBox")}
                      bind:checked={boxIsVisible}
                      title={boxIsVisible ? "Hide" : "Show"}
                      class="mx-1"
                    />
                  </div>
                {/if}
                {#if entity.ui.childs?.some((ann) => ann.is_mask)}
                  <div class="flex gap-2 mt-2 items-center">
                    <p class="font-light first-letter:uppercase">Mask</p>
                    <Checkbox
                      handleClick={() => handleIconClick("hidden", maskIsVisible, "CompressedRLE")}
                      bind:checked={maskIsVisible}
                      title={maskIsVisible ? "Hide" : "Show"}
                      class="mx-1"
                    />
                  </div>
                {/if}
                {#if entity.ui.childs?.some((ann) => ann.is_keypoints)}
                  <div class="flex gap-2 mt-2 items-center">
                    <p class="font-light first-letter:uppercase">Key points</p>
                    <Checkbox
                      handleClick={() => handleIconClick("hidden", keypointsIsVisible, "KeyPoints")}
                      bind:checked={keypointsIsVisible}
                      title={keypointsIsVisible ? "Hide" : "Show"}
                      class="mx-1"
                    />
                  </div>
                {/if}
              </div>
            </div>
          {/if}
          <UpdateFeatureInputs
            featureClass="objects"
            features={$features}
            {isEditing}
            {saveInputChange}
          />
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
