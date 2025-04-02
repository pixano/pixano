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
    BaseSchema,
    cn,
    Entity,
    IconButton,
    Item,
    Tracklet,
    WorkspaceType,
    type DisplayControl,
    type ObjectThumbnail,
    type SaveItem,
  } from "@pixano/core";

  import { datasetSchema } from "../../../../../apps/pixano/src/lib/stores/datasetStores";
  import { createFeature } from "../../lib/api/featuresApi";
  import {
    addOrUpdateSaveItem,
    defineObjectThumbnail,
    deleteObject,
    getTopEntity,
    highlightObject,
    toggleObjectDisplayControl,
  } from "../../lib/api/objectsApi";
  import { updateView } from "../../lib/api/videoApi";
  import { getDefaultDisplayFeat } from "../../lib/settings/defaultFeatures";
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
  import ChildCard from "./ChildCard.svelte";

  export let entity: Entity;
  let showIcons: boolean = false;
  let highlightState: string = "all";
  let isVisible: boolean = true;

  let hiddenTrack = entity.is_track ? entity.ui.displayControl.hidden : false;

  let displayName: string;
  $: if (entity) {
    const displayFeat = getDefaultDisplayFeat(entity);
    displayName = displayFeat ? `${displayFeat} (${entity.id})` : entity.id;
  }

  $: color = $colorScale[1](entity.id);

  const isAllowedChild = (child: Annotation): boolean => {
    if (child.ui.datasetItemType !== WorkspaceType.VIDEO) return true;
    if (
      child.is_type(BaseSchema.Tracklet) &&
      (child as Tracklet).data.start_timestep <= $currentFrameIndex &&
      (child as Tracklet).data.end_timestep >= $currentFrameIndex
    )
      return true;
    return false;
  };

  const isAllowableChild = (child: Annotation): boolean => {
    if (child.ui.datasetItemType !== WorkspaceType.VIDEO) return true;
    if (child.is_type(BaseSchema.Tracklet)) return true;
    return false;
  };

  const sortChilds = (a: Annotation, b: Annotation): number => {
    // first sort by BaseSchema -- convenient because lexical order is quite good:
    // BBox, CompressedRLE, KeyPoints, TextSpan, Tracklet
    let res = a.table_info.base_schema.localeCompare(b.table_info.base_schema);
    if (res === 0) {
      if (a.is_type(BaseSchema.Tracklet) && b.is_type(BaseSchema.Tracklet)) {
        //sort by view -- we know there is only one tracklet per view
        const orderMap = new Map(Object.keys($mediaViews).map((val, index) => [val, index]));
        res =
          (orderMap.get(a.data.view_ref.name) ?? Infinity) -
          (orderMap.get(b.data.view_ref.name) ?? Infinity);
      } else {
        if ("name" in a.data && "name" in b.data) {
          res = String(a.data["name"]).localeCompare(String(b.data["name"]));
        } else {
          res = a.id.localeCompare(b.id);
        }
      }
    }
    return res;
  };
  let allowedChilds: Annotation[];
  let allowableChilds: Annotation[] =
    entity.ui.childs?.filter((ann) => isAllowableChild(ann)) ?? [];

  $: if ($currentFrameIndex !== undefined) {
    allowedChilds = entity.ui.childs?.filter((ann) => isAllowedChild(ann)).sort(sortChilds) ?? [];
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
    highlightState = "all";
    for (const ann of entity.ui.childs ?? []) {
      if (ann.ui.displayControl.highlighted === "self") {
        highlightState = "self";
        break;
      }
      if (ann.ui.displayControl.highlighted === "none") {
        highlightState = "none";
      }
    }
    isVisible = entity.ui.childs?.some((ann) => !ann.ui.displayControl.hidden) || false;
  });

  const handleSetDisplayControl = (
    displayControlProperty: keyof DisplayControl,
    new_value: boolean,
    child: Annotation | null = null,
    other_anns_value: boolean | null = null,
  ) => {
    if (!child && displayControlProperty === "editing") {
      entity.ui.displayControl.editing = new_value;
    } else {
      let tracklet_childs_ids: string[] = [];
      if (child && child.is_type(BaseSchema.Tracklet)) {
        tracklet_childs_ids = (child as Tracklet).ui.childs.map((ann) => ann.id);
      }
      annotations.update((anns) =>
        anns.map((ann) => {
          if (
            (child && ann.id === child.id) ||
            tracklet_childs_ids.includes(ann.id) ||
            (!child && getTopEntity(ann).id === entity.id)
          ) {
            ann = toggleObjectDisplayControl(ann, displayControlProperty, new_value);
          } else if (other_anns_value !== null) {
            ann = toggleObjectDisplayControl(ann, displayControlProperty, other_anns_value);
          }
          return ann;
        }),
      );
    }
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
      //for canvas to reflect a name change, we need to refresh annotations store too
      annotations.update((anns) => anns);
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
    entity.ui.displayControl.open = true;
    const newFrameIndex = highlightObject(entity.id, highlightState === "self");
    if (newFrameIndex != $currentFrameIndex) {
      currentFrameIndex.set(newFrameIndex);
      updateView($currentFrameIndex);
    }
  };

  const onTrackVisClick = () => {
    if (entity.is_track) {
      entity.ui.displayControl.hidden = !entity.ui.displayControl.hidden;
      hiddenTrack = entity.ui.displayControl.hidden;
      //svelte hack to refresh
      entities.set($entities);
    }
  };

  const onEditIconClick = (child: Annotation | null = null) => {
    if (child) {
      handleSetDisplayControl("editing", !child.ui.displayControl.editing, child, false);
    } else {
      if (!entity.ui.displayControl.editing && highlightState !== "self") onColoredDotClick();
      handleSetDisplayControl("editing", !entity.ui.displayControl.editing);
    }
    if (!entity.ui.displayControl.editing) selectedTool.set(panTool);
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
  on:mouseleave={() => (showIcons = entity.ui.displayControl.open ?? false)}
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
        on:click={() => handleSetDisplayControl("hidden", isVisible)}
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
          "text-slate-300": highlightState === "none" && $selectedTool.type === ToolType.Fusion,
        })}
        title="{entity.table_info.base_schema} ({entity.id})"
      >
        {displayName}
      </span>
    </div>
    <div
      class={cn(
        "flex-shrink-0 flex items-center justify-end",
        showIcons || entity.ui.displayControl.editing
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
      {#if showIcons || entity.ui.displayControl.editing}
        {#if $selectedTool.type !== ToolType.Fusion}
          <IconButton
            tooltipContent="Edit object"
            selected={entity.ui.displayControl.editing}
            on:click={() => onEditIconClick()}
          >
            <Pencil class="h-4" />
          </IconButton>
        {/if}
        <IconButton tooltipContent="Delete object" redconfirm on:click={() => deleteObject(entity)}>
          <Trash2 class="h-4" />
        </IconButton>
      {/if}
      {#if entity.is_track && (showIcons || entity.ui.displayControl.editing || hiddenTrack)}
        <IconButton
          tooltipContent={hiddenTrack ? "Show track" : "Hide track"}
          on:click={onTrackVisClick}
        >
          {#if hiddenTrack}<ListPlus class="h-4" />{:else}<ListX class="h-4" />{/if}
        </IconButton>
      {/if}
      <IconButton
        on:click={() => (entity.ui.displayControl.open = !entity.ui.displayControl.open)}
        tooltipContent={entity.ui.displayControl.open ? "Hide features" : "Show features"}
      >
        <ChevronRight
          class={cn("transition", { "rotate-90": entity.ui.displayControl.open })}
          strokeWidth={1}
        />
      </IconButton>
    </div>
  </div>
  {#if entity.ui.displayControl.open}
    <div class="pl-5 text-slate-800 bg-white">
      <div
        class="border-l-4 border-dashed border-red-400 pl-4 flex flex-col gap-4 pb-2"
        style="border-color:{color}"
      >
        <div class="flex flex-col gap-2">
          <div class="w-full block">
            <p class="font-medium">Features</p>
            <UpdateFeatureInputs
              featureClass="objects"
              features={$features}
              isEditing={entity.ui.displayControl.editing ?? false}
              {saveInputChange}
            />
          </div>
          <p class="font-medium">Objects ({allowableChilds.length})</p>
          <div class="flex flex-col">
            {#if entity.ui.childs?.some((ann) => ann.ui.datasetItemType === WorkspaceType.VIDEO)}
              <p class="text-center italic">
                {allowedChilds.length > 0 ? allowedChilds.length : "No"}
                object{allowedChilds.length === 1 ? "" : "s"}
                visible on frame {$currentFrameIndex}
              </p>
            {/if}
            {#each allowedChilds as child}
              <ChildCard {entity} {child} {handleSetDisplayControl} {onEditIconClick} />
            {/each}
          </div>
          <p class="font-medium">Thumbnails</p>
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
