<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { ChevronRight, Eye, EyeOff, ListPlus, ListX, Pencil, Trash2 } from "lucide-svelte";
  import { onDestroy } from "svelte";
  import { derived } from "svelte/store";

  import { TextSpansContent } from "@pixano/canvas2d";
  import { ToolType } from "@pixano/canvas2d/src/tools";
  import {
    Annotation,
    BaseSchema,
    Card,
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
  let childsPanelOpen = true;
  let featuresPanelOpen = !entity.ui.childs?.some(
    (ann) => ann.ui.datasetItemType === WorkspaceType.IMAGE_TEXT_ENTITY_LINKING,
  );
  let hiddenTrack = entity.is_track ? entity.ui.displayControl.hidden : false;

  let displayName: string;
  $: if (entity) {
    const displayFeat = getDefaultDisplayFeat(entity);
    displayName = displayFeat ? `${displayFeat} (${entity.id})` : entity.id;
  }
  $: color = $colorScale[1](entity.id);
  $: entity.ui.displayControl.open = highlightState === "self";

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
      if (entity.is_track) {
        if ($currentFrameIndex !== null) {
          child_anns = entity.ui.childs!.filter(
            (ann) =>
              !ann.is_type(BaseSchema.Tracklet) && ann.ui.frame_index! === $currentFrameIndex,
          );
        } else {
          child_anns = entity.ui.childs!.filter((ann) => !ann.is_type(BaseSchema.Tracklet));
        }
      } else {
        child_anns = entity.ui.childs!;
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
      feats[entity.id] = createFeature(entity, $datasetSchema, entity.table_info.name);

      return Object.values(feats).flat();
    },
  );

  const unsubscribeAnnotations = annotations.subscribe(() => {
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
    if (
      [BaseSchema.Track, BaseSchema.Entity, BaseSchema.MultiModalEntity].includes(
        obj.table_info.base_schema,
      )
    ) {
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
      featuresPanelOpen = true;
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
        (ann) =>
          (ann.is_type(BaseSchema.BBox) || ann.is_type(BaseSchema.Mask)) &&
          ann.data.view_ref.name === view,
      );
      if (highlightedBoxesByView) {
        // Prefer BBox if available for this view
        const preferredBox =
          highlightedBoxesByView.find((ann) => ann.is_type(BaseSchema.BBox)) ||
          highlightedBoxesByView[Math.floor(highlightedBoxesByView.length / 2)];
        if (preferredBox) {
          const selectedThumbnail = defineObjectThumbnail($itemMetas, $mediaViews, preferredBox);
          if (selectedThumbnail) {
            thumbnails.push(selectedThumbnail);
          }
        }
      }
    }
  };
  const unsubscribeEntities = entities.subscribe(() => setThumbnails());

  onDestroy(() => {
    unsubscribeAnnotations();
    unsubscribeEntities();
  });
</script>

<Card.Root
  class={cn(
    "shadow-none rounded-xl border-border/50 overflow-hidden transition-all duration-200",
    highlightState === "self"
      ? "ring-1 ring-primary/20 bg-primary/[0.03]"
      : "hover:bg-accent/40 hover:border-border",
  )}
  style={`
    border-left: ${highlightState === "self" ? `4px solid ${color}` : "4px solid transparent"};
  `}
  on:mouseenter={() => (showIcons = true)}
  on:mouseleave={() => (showIcons = entity.ui.displayControl.open ?? false)}
  id={`card-object-${entity.id}`}
>
  <Card.Header class="p-2 py-1.5 flex-row space-y-0 items-center justify-between gap-2">
    <div class="flex-[1_1_auto] flex items-center overflow-hidden min-w-0 gap-1.5">
      <IconButton
        on:click={() => handleSetDisplayControl("hidden", isVisible)}
        tooltipContent={isVisible ? "Hide object" : "Show object"}
        class="opacity-70 hover:opacity-100"
      >
        {#if isVisible}
          <Eye class="h-4 w-4" />
        {:else}
          <EyeOff class="h-4 w-4" />
        {/if}
      </IconButton>
      {#if thumbnails.length > 0}
        {@const thumb = thumbnails[0]}
        {@const innerSize = 44}
        {@const cropW = thumb.coords[2] * thumb.baseImageDimensions.width}
        {@const cropH = thumb.coords[3] * thumb.baseImageDimensions.height}
        {@const cropAspect = cropW / cropH}
        {@const fitW = cropAspect >= 1 ? innerSize : innerSize * cropAspect}
        {@const fitH = cropAspect >= 1 ? innerSize / cropAspect : innerSize}
        {@const imgScale = fitW / cropW}
        {@const imgW = thumb.baseImageDimensions.width * imgScale}
        {@const imgH = thumb.baseImageDimensions.height * imgScale}
        {@const offX = -thumb.coords[0] * thumb.baseImageDimensions.width * imgScale}
        {@const offY = -thumb.coords[1] * thumb.baseImageDimensions.height * imgScale}
        <button
          class="flex-shrink-0 flex items-center justify-center rounded-lg overflow-hidden
                 transition-all duration-200 hover:ring-2 hover:ring-primary/30"
          style="width: 48px; height: 48px; border: 2.5px solid {color};
                 background: hsl(var(--muted) / 0.8);"
          title="Highlight object"
          on:click={onColoredDotClick}
        >
          <div class="relative overflow-hidden" style="width: {fitW}px; height: {fitH}px;">
            <img
              src="/{thumb.uri}"
              alt=""
              class="absolute max-w-none"
              style="width: {imgW}px; height: {imgH}px;
                     left: {offX}px; top: {offY}px;"
            />
          </div>
        </button>
      {:else}
        <button
          class="rounded-full w-3 h-3 mx-1 flex-shrink-0 ring-2 ring-white shadow-sm
                 transition-transform hover:scale-125"
          style="background:{color}"
          title="Highlight object"
          on:click={onColoredDotClick}
        />
      {/if}
      <div class="flex flex-col min-w-0 overflow-hidden">
        <span
          class={cn("truncate text-[13px] font-semibold leading-tight transition-colors", {
            "text-foreground": highlightState !== "none",
            "text-muted-foreground":
              highlightState === "none" && $selectedTool.type === ToolType.Fusion,
          })}
          title="{entity.table_info.base_schema} ({entity.id})"
        >
          {displayName}
        </span>
        <span
          class="text-[10px] text-muted-foreground uppercase tracking-tight font-medium opacity-70"
        >
          {entity.table_info.base_schema}
        </span>
      </div>
    </div>
    <div class="flex-shrink-0 flex items-center justify-end gap-0.5">
      <div
        class={cn(
          "flex items-center gap-0.5 transition-opacity duration-200",
          showIcons || entity.ui.displayControl.editing ? "opacity-100" : "opacity-0",
        )}
      >
        {#if showIcons || entity.ui.displayControl.editing}
          <IconButton
            tooltipContent="Delete object"
            redconfirm
            on:click={() => deleteObject(entity)}
            class="text-muted-foreground hover:text-destructive"
          >
            <Trash2 class="h-4 w-4" />
          </IconButton>
        {/if}
        {#if entity.is_track && (showIcons || entity.ui.displayControl.editing || hiddenTrack)}
          <IconButton
            tooltipContent={hiddenTrack ? "Show track" : "Hide track"}
            on:click={onTrackVisClick}
            class="text-muted-foreground"
          >
            {#if hiddenTrack}<ListPlus class="h-4 w-4" />{:else}<ListX class="h-4 w-4" />{/if}
          </IconButton>
        {/if}
      </div>
      <IconButton
        on:click={() => (entity.ui.displayControl.open = !entity.ui.displayControl.open)}
        tooltipContent={entity.ui.displayControl.open ? "Hide features" : "Show features"}
        class="text-muted-foreground"
      >
        <ChevronRight
          class={cn("transition-transform duration-200", {
            "rotate-90": entity.ui.displayControl.open,
          })}
          strokeWidth={2}
        />
      </IconButton>
    </div>
  </Card.Header>
  {#if entity.ui.displayControl.open}
    <Card.Content class="p-3 bg-muted/40 border-t border-border/40 space-y-4">
      <!-- Features Section -->
      <div class="space-y-2">
        <div class="flex items-center justify-between py-1 border-b border-border/30">
          <h4 class="text-[10px] font-bold uppercase tracking-[0.05em] text-muted-foreground/80">
            Properties
          </h4>
          <div class="flex items-center gap-1">
            {#if $selectedTool.type !== ToolType.Fusion}
              <IconButton
                tooltipContent="Edit properties"
                selected={entity.ui.displayControl.editing}
                on:click={() => onEditIconClick()}
                class="h-6 w-6"
              >
                <Pencil class="h-3.5 w-3.5" />
              </IconButton>
            {/if}
            <IconButton
              on:click={() => {
                featuresPanelOpen = !featuresPanelOpen;
                entity.ui.displayControl.editing = false;
              }}
              tooltipContent={featuresPanelOpen ? "Collapse" : "Expand"}
              class="h-6 w-6"
            >
              <ChevronRight
                class={cn("h-4 w-4 transition-transform duration-200", {
                  "rotate-90": featuresPanelOpen,
                })}
              />
            </IconButton>
          </div>
        </div>
        {#if featuresPanelOpen}
          <div class="pl-1 pt-1">
            <UpdateFeatureInputs
              featureClass="objects"
              features={$features}
              isEditing={entity.ui.displayControl.editing ?? false}
              {saveInputChange}
            />
          </div>
        {/if}
      </div>

      <!-- Objects Section -->
      <div class="space-y-2">
        <div class="flex items-center justify-between py-1 border-b border-border/30">
          <h4 class="text-[10px] font-bold uppercase tracking-[0.05em] text-muted-foreground/80">
            Annotations
            <span class="ml-1.5 tabular-nums opacity-60">
              ({allowableChilds.length})
            </span>
          </h4>
          <IconButton
            on:click={() => (childsPanelOpen = !childsPanelOpen)}
            tooltipContent={childsPanelOpen ? "Collapse" : "Expand"}
            class="h-6 w-6"
          >
            <ChevronRight
              class={cn("h-4 w-4 transition-transform duration-200", {
                "rotate-90": childsPanelOpen,
              })}
            />
          </IconButton>
        </div>

        {#if childsPanelOpen}
          <div class="space-y-1 pl-1">
            {#if entity.ui.childs?.some((ann) => ann.ui.datasetItemType === WorkspaceType.VIDEO)}
              <p
                class="text-[11px] text-center text-muted-foreground/70 italic py-1 bg-muted/20 rounded"
              >
                {allowedChilds.length > 0 ? allowedChilds.length : "No"}
                object{allowedChilds.length === 1 ? "" : "s"}
                on frame {$currentFrameIndex}
              </p>
            {/if}
            {#each allowedChilds as child}
              <ChildCard {entity} {child} {handleSetDisplayControl} {onEditIconClick} />
            {/each}
          </div>
        {/if}
        <TextSpansContent annotations={entity.ui.childs} />
      </div>
    </Card.Content>
  {/if}
</Card.Root>
