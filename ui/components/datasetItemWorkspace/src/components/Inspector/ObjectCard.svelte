<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { ChevronRight, Eye, EyeOff, ListPlus, ListX, Pencil, Trash2 } from "lucide-svelte";
  import { derived } from "svelte/store";

  import { TextSpansContent, Thumbnail } from "@pixano/canvas2d";
  import { ToolType } from "@pixano/canvas2d/src/tools";
  import {
    Annotation,
    Entity,
    Item,
    WorkspaceType,
    type DisplayControl,
    type ObjectThumbnail,
    type SaveItem,
  } from "@pixano/core";
  import { BaseSchema, cn, IconButton } from "@pixano/core/src";

  import { datasetSchema } from "../../../../../apps/pixano/src/lib/stores/datasetStores";
  import { createFeature } from "../../lib/api/featuresApi";
  import {
    addOrUpdateSaveItem,
    defineObjectThumbnail,
    getTopEntity,
    highlightObject,
    toggleObjectDisplayControl,
  } from "../../lib/api/objectsApi";
  import { updateView } from "../../lib/api/videoApi";
  import { panTool } from "../../lib/settings/selectionTools";
  import {
    annotations,
    colorScale,
    entities,
    itemMetas,
    mediaViews,
    saveData,
    selectedTool,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import { currentFrameIndex } from "../../lib/stores/videoViewerStores";
  import type { Feature } from "../../lib/types/datasetItemWorkspaceTypes";
  import UpdateFeatureInputs from "../Features/UpdateFeatureInputs.svelte";
  import DisplayCheckbox from "./DisplayCheckbox.svelte";

  export let entity: Entity;
  let open: boolean = false;
  let showIcons: boolean = false;
  let highlightState: string = "all";
  let isEditing: boolean = false;
  let isVisible: boolean = true;
  let boxIsVisible: boolean = true;
  let maskIsVisible: boolean = true;
  let keypointsIsVisible: boolean = true;
  let textSpansIsVisible: boolean = true;

  let hiddenTrack = entity.is_track ? entity.ui.hidden : false;

  $: displayName =
    (entity.data.name
      ? (entity.data.name as string) + " "
      : entity.data.category
        ? (entity.data.category as string) + " "
        : "") + `(${entity.id})`;

  $: color = $colorScale[1](entity.id);

  $: if (isEditing) {
    open = true;
  } else {
    open = false;
  }

  const features = derived(
    [currentFrameIndex, entities, annotations],
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    ([$currentFrameIndex, $entities, $annotations]) => {
      //get all features from Top entity (obj) to evental sub entities and annotations
      //let anns_features: Record<string, Feature[]> = {};
      let feats: Record<string, Feature[]> = {};
      let child_anns: Annotation[] = [];
      if ($currentFrameIndex !== null) {
        child_anns = entity.ui.childs!.filter(
          (ann) => !ann.is_type(BaseSchema.Tracklet) && ann.ui.frame_index! === $currentFrameIndex,
        );
      } else {
        child_anns = entity.ui.childs!.filter((ann) => !ann.is_type(BaseSchema.Tracklet));
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
    if (entity.ui.childs?.some((ann) => ann.ui.highlighted === "self")) {
      highlightState = "self";
    } else if (entity.ui.childs?.some((ann) => ann.ui.highlighted === "none")) {
      highlightState = "none";
    } else {
      highlightState = "all";
    }
    isEditing = entity.ui.childs?.some((ann) => ann.ui.displayControl?.editing) || false;
    isVisible = entity.ui.childs?.some((ann) => !ann.ui.displayControl?.hidden) || false;
    boxIsVisible =
      entity.ui.childs?.some(
        (ann) => ann.is_type(BaseSchema.BBox) && !ann.ui.displayControl?.hidden,
      ) || false;
    maskIsVisible =
      entity.ui.childs?.some(
        (ann) => ann.is_type(BaseSchema.Mask) && !ann.ui.displayControl?.hidden,
      ) || false;
    keypointsIsVisible =
      entity.ui.childs?.some(
        (ann) => ann.is_type(BaseSchema.Keypoints) && !ann.ui.displayControl?.hidden,
      ) || false;
    textSpansIsVisible =
      entity.ui.childs?.some(
        (ann) => ann.is_type(BaseSchema.TextSpan) && !ann.ui.displayControl?.hidden,
      ) || false;
  });

  const handleSetAnnotationDisplayControl = (
    displayControlProperty: keyof DisplayControl,
    isVisible: boolean,
    base_schema: BaseSchema | null = null,
  ) => {
    annotations.update((anns) =>
      anns.map((ann) => {
        if (displayControlProperty === "editing") {
          //no change on non current anns for video
          if (ann.ui.datasetItemType === WorkspaceType.VIDEO) {
            if (ann.ui.frame_index !== $currentFrameIndex) return ann;
          }

          if (getTopEntity(ann).id === entity.id) {
            if (isVisible) {
              ann.ui.highlighted = "self";
            } else {
              ann.ui.highlighted = "all";
            }
          } else {
            ann.ui.highlighted = "none";
          }

          ann.ui.displayControl = {
            ...ann.ui.displayControl,
            editing: false,
          };
        }
        if (
          getTopEntity(ann).id === entity.id &&
          (!base_schema || (base_schema && ann.table_info.base_schema === base_schema))
        ) {
          ann = toggleObjectDisplayControl(ann, displayControlProperty, isVisible);
        }
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
    if ([BaseSchema.Track, BaseSchema.Entity].includes(obj.table_info.base_schema)) {
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
    } else if (obj.table_info.base_schema === BaseSchema.Item) {
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
    const newFrameIndex = highlightObject(entity.id, highlightState === "self");
    if (newFrameIndex != $currentFrameIndex) {
      currentFrameIndex.set(newFrameIndex);
      updateView($currentFrameIndex);
    }
  };

  const onTrackVisClick = () => {
    if (entity.is_track) {
      entity.ui.hidden = !entity.ui.hidden;
      hiddenTrack = entity.ui.hidden;
      //svelte hack to refresh
      entities.set($entities);
    }
  };

  const onEditIconClick = () => {
    onColoredDotClick();
    handleSetAnnotationDisplayControl("editing", !isEditing);
    if (!isEditing) selectedTool.set(panTool);
  };

  let thumbnails: ObjectThumbnail[] = [];
  const setThumbnails = () => {
    thumbnails = [];
    for (const view of Object.keys($mediaViews)) {
      const highlightedBoxesByView = entity.ui.childs?.filter(
        (ann) => ann.is_type(BaseSchema.BBox) && ann.data.view_ref.name == view,
      );
      if (highlightedBoxesByView) {
        const selectedBox = highlightedBoxesByView[Math.floor(highlightedBoxesByView.length / 2)];
        if (selectedBox) {
          const selectedThumbnail = defineObjectThumbnail($itemMetas, $mediaViews, selectedBox);
          if (selectedThumbnail) {
            thumbnails.push(selectedThumbnail);
          }
        }
      }
    }
  };
  entities.subscribe(() => setThumbnails());
</script>

<article
  on:mouseenter={() => (showIcons = true)}
  on:mouseleave={() => (showIcons = open)}
  id={`card-object-${entity.id}`}
>
  <div
    class={cn("flex items-center mt-1 rounded justify-between bg-white border-2 overflow-hidden")}
    style={`
      background: ${highlightState === "self" ? `${color}8a` : "white"};
      border-color: ${highlightState === "self" ? color : "transparent"}
    `}
  >
    <div class="flex-[1_1_auto] flex items-center overflow-hidden min-w-0">
      <IconButton
        on:click={() => handleSetAnnotationDisplayControl("hidden", isVisible)}
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
      <span
        class={cn("truncate flex-auto overflow-hidden overflow-ellipsis whitespace-nowrap", {
          "text-slate-800": highlightState !== "none",
          "text-slate-500": highlightState === "none" && $selectedTool.type !== ToolType.Fusion,
          "text-slate-300": highlightState === "none" && $selectedTool.type === ToolType.Fusion,
        })}
      >
        {displayName}
      </span>
    </div>
    <div
      class={cn(
        "flex-shrink-0 flex items-center justify-end",
        showIcons || isEditing
          ? entity.is_track
            ? $selectedTool.type !== ToolType.Fusion
              ? "basis-[160px]"
              : "basis-[120px]"
            : "basis-[120px]"
          : entity.is_track && hiddenTrack
            ? "basis-[80px]"
            : "basis-[40px]",
      )}
      style="min-width: 40px;"
    >
      {#if showIcons || isEditing}
        {#if $selectedTool.type !== ToolType.Fusion}
          <IconButton tooltipContent="Edit object" selected={isEditing} on:click={onEditIconClick}>
            <Pencil class="h-4" />
          </IconButton>
        {/if}
        <IconButton tooltipContent="Delete object" on:click={deleteObject}>
          <Trash2 class="h-4" />
        </IconButton>
      {/if}
      {#if entity.is_track && (showIcons || isEditing || hiddenTrack)}
        <IconButton
          tooltipContent={hiddenTrack ? "Show track" : "Hide track"}
          on:click={onTrackVisClick}
        >
          {#if hiddenTrack}<ListPlus class="h-4" />{:else}<ListX class="h-4" />{/if}
        </IconButton>
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
    <div class="pl-5 text-slate-800 bg-white">
      <div
        class="border-l-4 border-dashed border-red-400 pl-4 pb-4 pt-4 flex flex-col gap-4"
        style="border-color:{color}"
      >
        <div class="flex flex-col gap-2">
          <div>
            <p class="font-medium">Display</p>
            <div class="flex gap-4">
              <DisplayCheckbox
                isAnnotationEmpty={!entity.ui.childs?.some((ann) => ann.is_type(BaseSchema.BBox))}
                {handleSetAnnotationDisplayControl}
                annotationIsVisible={boxIsVisible}
                annotationName="Bounding box"
                base_schema={BaseSchema.BBox}
              />
              <DisplayCheckbox
                isAnnotationEmpty={!entity.ui.childs?.some((ann) => ann.is_type(BaseSchema.Mask))}
                {handleSetAnnotationDisplayControl}
                annotationIsVisible={maskIsVisible}
                annotationName="Segmentation mask"
                base_schema={BaseSchema.Mask}
              />
              <DisplayCheckbox
                isAnnotationEmpty={!entity.ui.childs?.some((ann) =>
                  ann.is_type(BaseSchema.Keypoints),
                )}
                {handleSetAnnotationDisplayControl}
                annotationIsVisible={keypointsIsVisible}
                annotationName="Keypoints"
                base_schema={BaseSchema.Keypoints}
              />
              <DisplayCheckbox
                isAnnotationEmpty={!entity.ui.childs?.some((ann) =>
                  ann.is_type(BaseSchema.TextSpan),
                )}
                {handleSetAnnotationDisplayControl}
                annotationIsVisible={textSpansIsVisible}
                annotationName="Text span"
                base_schema={BaseSchema.TextSpan}
              />
            </div>
          </div>
          <UpdateFeatureInputs
            featureClass="objects"
            features={$features}
            {isEditing}
            {saveInputChange}
          />
          {#each thumbnails as thumbnail}
            <Thumbnail
              imageDimension={thumbnail.baseImageDimensions}
              coords={thumbnail.coords}
              imageUrl={`/${thumbnail.uri}`}
              minSide={150}
              maxWidth={200}
              maxHeight={200}
            />
            {#if Object.keys($mediaViews).length > 1}
              <span class="text-center italic">{thumbnail.view}</span>
            {/if}
          {/each}
          <TextSpansContent annotations={entity.ui.childs} />
        </div>
      </div>
    </div>
  {/if}
</article>
