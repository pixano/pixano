<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { slide } from "svelte/transition";
  import { cubicOut } from "svelte/easing";
  import {
    CaretRight,
    Eye,
    EyeClosed,
    Ghost,
    GitCommit,
    LineSegments,
    ListPlus,
    ListDashes,
    Pencil,
    Square,
    TextT,
    Trash,
  } from "phosphor-svelte";

  import UpdateFeatureInputs from "../Features/UpdateFeatureInputs.svelte";
  import ChildCard from "./ChildCard.svelte";
  import {
    setEntityDisplayControl as setDisplayCtrl,
    handleSetDisplayControl as handleSetDC,
    saveInputChange as saveInput,
  } from "./entityCardOps";
  import { currentFrameIndex } from "$lib/stores/videoStores.svelte";
  import {
    annotations,
    colorScale,
    entities,
    highlightedEntity,
    itemMetas,
    mediaViews,
    selectedTool,
  } from "$lib/stores/workspaceStores.svelte";
  import { panTool, ToolType } from "$lib/tools";
  import type { Feature } from "$lib/types/workspace";
  import {
    Annotation,
    BaseSchema,
    Card,
    cn,
    entityHasTracklets,
    Entity,
    IconButton,
    Item,
    Tracklet,
    WorkspaceType,
    type AnnotationThumbnail,
    type DisplayControl,
  } from "$lib/ui";
  import { keypointsIcon } from "$lib/assets";
  import { defineAnnotationThumbnail } from "$lib/utils/entityLookupUtils";
  import { deleteEntity } from "$lib/utils/entityDeletion";
  import { createFeature } from "$lib/utils/featureMapping";
  import { highlightEntity } from "$lib/utils/highlightOperations";
  import { updateView } from "$lib/utils/videoOperations";
  import { getWorkspaceContext } from "$lib/workspace/context";

  // ─── Hidden fields: internal plumbing excluded from Attributes tab ──────────
  const HIDDEN_FIELDS = new Set([
    "item_id",
    "entity_id",
    "parent_id",
    "source_id",
    "source_type",
    // source_name & source_metadata are shown on ChildCard, NOT hidden
    "tracklet_id",
    "entity_dynamic_state_id",
    "frame_id",
    "frame_index",
    "view_id",
    "view_name",
    "inference_metadata",
    // Schema-specific raw data (shown via specialized ChildCard visualizations)
    "coords",
    "format",
    "is_normalized",
    "confidence",
    "size",
    "counts",
    "spans_start",
    "spans_end",
    "mention",
    "template_id",
    "states",
    "start_frame",
    "end_frame",
    "start_timestamp",
    "end_timestamp",
  ]);

  // ─── Annotation type display metadata ───────────────────────────────────────
  const TYPE_META: Record<string, { label: string; color: string }> = {
    [BaseSchema.BBox]: { label: "BBox", color: "bg-blue-500/15 text-blue-400" },
    [BaseSchema.Mask]: { label: "Mask", color: "bg-purple-500/15 text-purple-400" },
    [BaseSchema.MultiPath]: { label: "MultiPath", color: "bg-orange-500/15 text-orange-400" },
    [BaseSchema.Keypoints]: { label: "Keypoints", color: "bg-teal-500/15 text-teal-400" },
    [BaseSchema.TextSpan]: { label: "Text", color: "bg-amber-500/15 text-amber-400" },
    [BaseSchema.Tracklet]: { label: "Track", color: "bg-cyan-500/15 text-cyan-400" },
  };

  interface Props {
    entity: Entity;
  }

  let { entity }: Props = $props();
  const { manifest } = getWorkspaceContext();
  let detailsTab = $state<"attributes" | "annotations">("attributes");

  const color = $derived(colorScale.value[1](entity.id));
  const entityDisplayControl = $derived.by(() => {
    void entities.value;
    return entity.ui.displayControl;
  });
  const isExpanded = $derived(entityDisplayControl.open ?? false);

  // ─── Child filtering & sorting (unchanged logic) ───────────────────────────
  const isAllowedChild = (child: Annotation): boolean => {
    if (child.ui.datasetItemType !== WorkspaceType.VIDEO) return true;
    if (
      child.is_type(BaseSchema.Tracklet) &&
      (child as Tracklet).data.start_frame <= currentFrameIndex.value &&
      (child as Tracklet).data.end_frame >= currentFrameIndex.value
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
    let res = a.table_info.base_schema.localeCompare(b.table_info.base_schema);
    if (res === 0) {
      if (a.is_type(BaseSchema.Tracklet) && b.is_type(BaseSchema.Tracklet)) {
        const orderMap = new Map(Object.keys(mediaViews.value).map((val, index) => [val, index]));
        res =
          (orderMap.get(a.data.view_name) ?? Infinity) -
          (orderMap.get(b.data.view_name) ?? Infinity);
      } else {
        if ("name" in a.data && "name" in b.data) {
          const getComparableName = (value: unknown): string => {
            if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
              return String(value);
            }
            return "";
          };
          res = getComparableName(a.data["name"]).localeCompare(getComparableName(b.data["name"]));
        } else {
          res = a.id.localeCompare(b.id);
        }
      }
    }
    return res;
  };

  const totalAllowableChildCount = $derived.by(() => {
    return entity.ui.childs?.filter((ann) => isAllowableChild(ann)).length ?? 0;
  });

  const allowedChilds = $derived.by(() => {
    if (!isExpanded) return [];
    if (currentFrameIndex.value === undefined) return [];
    return entity.ui.childs?.filter((ann) => isAllowedChild(ann)).sort(sortChilds) ?? [];
  });

  // ─── Annotation type summary for header pills ──────────────────────────────
  const annotationTypeSummary = $derived.by(() => {
    const counts: Record<string, number> = {};
    for (const ann of entity.ui.childs ?? []) {
      if (!isAllowableChild(ann)) continue;
      const schema = ann.table_info.base_schema;
      counts[schema] = (counts[schema] ?? 0) + 1;
    }
    return counts;
  });

  // ─── Detect text-only entities (for typographic fallback thumbnail) ─────────
  const hasOnlyTextSpans = $derived.by(() => {
    const childs = entity.ui.childs ?? [];
    if (childs.length === 0) return false;
    return childs.every((ann) => ann.is_type(BaseSchema.TextSpan));
  });

  // ─── Highlight, visibility, tool state ──────────────────────────────────────
  const selectedToolType = $derived(selectedTool.value?.type ?? ToolType.Pan);
  const highlightState = $derived.by<"all" | "self" | "none">(() => {
    if (selectedToolType === ToolType.Pan) {
      return highlightedEntity.value === entity.id ? "self" : "all";
    }
    void annotations.value;
    let nextHighlightState: "all" | "self" | "none" = "all";
    for (const ann of entity.ui.childs ?? []) {
      if (ann.ui.displayControl.highlighted === "self") {
        nextHighlightState = "self";
        break;
      }
      if (ann.ui.displayControl.highlighted === "none") {
        nextHighlightState = "none";
      }
    }
    return nextHighlightState;
  });
  const isVisible = $derived.by(() => {
    void annotations.value; // reactive bridge: recompute when annotations are toggled
    return entity.ui.childs?.some((ann) => !ann.ui.displayControl.hidden) || false;
  });
  const hiddenTrack = $derived(entityHasTracklets(entity) ? entityDisplayControl.hidden : false);

  // ─── Entity-only features (Attributes tab) ──────────────────────────────────
  // Clean labels: no bracketed prefix since the Attributes tab is entity-only.
  const entityFeatures = $derived.by(() => {
    if (!isExpanded) return [];
    void entities.value;
    void annotations.value;
    return createFeature(entity, manifest, "").filter((f) => !HIDDEN_FIELDS.has(f.name));
  });

  // ─── Per-annotation features map (Annotations tab, inside each ChildCard) ──
  // Keys are annotation IDs. Values contain both the annotation's own custom
  // attributes and any sub-entity attributes (when the annotation's entity_id
  // differs from the top-level entity).
  const annotationFeaturesMap = $derived.by(() => {
    if (!isExpanded) return new Map<string, { annFeats: Feature[]; subEntityFeats: Feature[] }>();
    const currentEntities = entities.value;
    const frameIndex = currentFrameIndex.value;
    void annotations.value;
    const result = new Map<string, { annFeats: Feature[]; subEntityFeats: Feature[] }>();
    const seenSubEntities = new Map<string, Feature[]>();

    let childAnns: Annotation[] = [];
    if (entityHasTracklets(entity)) {
      if (frameIndex !== null) {
        childAnns = (entity.ui.childs ?? []).filter(
          (ann) => !ann.is_type(BaseSchema.Tracklet) && ann.ui.frame_index === frameIndex,
        );
      } else {
        childAnns = (entity.ui.childs ?? []).filter((ann) => !ann.is_type(BaseSchema.Tracklet));
      }
    } else {
      childAnns = entity.ui.childs ?? [];
    }

    for (const ann of childAnns) {
      // Annotation's own custom features (no prefix -- ChildCard provides context)
      const annFeats = createFeature(ann, manifest, "").filter((f) => !HIDDEN_FIELDS.has(f.name));

      // Sub-entity features (if annotation belongs to a different entity)
      let subEntityFeats: Feature[] = [];
      if (ann.data.entity_id !== entity.id) {
        if (seenSubEntities.has(ann.data.entity_id)) {
          subEntityFeats = seenSubEntities.get(ann.data.entity_id)!;
        } else {
          const subentity = currentEntities.find((ent) => ent.id === ann.data.entity_id);
          if (subentity) {
            subEntityFeats = createFeature(subentity, manifest, "").filter(
              (f) => !HIDDEN_FIELDS.has(f.name),
            );
            seenSubEntities.set(ann.data.entity_id, subEntityFeats);
          }
        }
      }

      result.set(ann.id, { annFeats, subEntityFeats });
    }
    return result;
  });

  // ─── Thumbnails ─────────────────────────────────────────────────────────────
  const thumbnails = $derived.by(() => {
    void entities.value;
    void annotations.value;
    const currentViews = mediaViews.value;
    const currentItemMetas = itemMetas.value;
    const annotationThumbnails: AnnotationThumbnail[] = [];
    for (const view of Object.keys(currentViews)) {
      const highlightedBoxesByView = entity.ui.childs?.filter(
        (ann) =>
          (ann.is_type(BaseSchema.BBox) || ann.is_type(BaseSchema.Mask) || ann.is_type(BaseSchema.MultiPath)) &&
          ann.data.view_name === view,
      );
      if (highlightedBoxesByView) {
        const preferredBox =
          highlightedBoxesByView.find((ann) => ann.is_type(BaseSchema.BBox)) ||
          highlightedBoxesByView[Math.floor(highlightedBoxesByView.length / 2)];
        if (preferredBox) {
          const selectedThumbnail = defineAnnotationThumbnail(
            currentItemMetas,
            currentViews,
            preferredBox,
          );
          if (selectedThumbnail) annotationThumbnails.push(selectedThumbnail);
        }
      }
    }
    return annotationThumbnails;
  });

  // ─── Actions ────────────────────────────────────────────────────────────────
  const setEntityDisplayControl = (updates: Partial<DisplayControl>) => {
    setDisplayCtrl(entity.id, entityDisplayControl, updates, entities);
  };

  const handleSetDisplayControl = (
    displayControlProperty: keyof DisplayControl,
    new_value: boolean,
    child: Annotation | null = null,
    other_anns_value: boolean | null = null,
  ) => {
    handleSetDC(entity.id, entityDisplayControl, displayControlProperty, new_value, child, other_anns_value, entities, annotations);
  };

  const saveInputChange = (
    value: string | boolean | number,
    propertyName: string,
    obj: Item | Entity | Annotation,
  ) => {
    saveInput(value, propertyName, obj, entities, annotations);
  };

  const focusEntity = () => {
    const newFrameIndex = highlightEntity(entity.id, false, false);
    if (newFrameIndex != currentFrameIndex.value) {
      currentFrameIndex.value = newFrameIndex;
      updateView(currentFrameIndex.value);
    }
  };

  const onColoredDotClick = () => {
    setEntityDisplayControl({ open: true });
    focusEntity();
  };

  const onCardClick = (event: MouseEvent) => {
    const target = event.target as HTMLElement | null;
    if (target?.closest("button, input, select, textarea, [role='button']")) return;
    onColoredDotClick();
  };

  const onTrackVisClick = () => {
    if (!entityHasTracklets(entity)) return;
    setEntityDisplayControl({ hidden: !hiddenTrack });
  };

  const onEditIconClick = (child: Annotation | null = null) => {
    if (child) {
      handleSetDisplayControl("editing", !child.ui.displayControl.editing, child, false);
    } else {
      detailsTab = "attributes";
      if (!entityDisplayControl.editing && highlightState !== "self") onColoredDotClick();
      handleSetDisplayControl("editing", !entityDisplayControl.editing);
    }
    if (!entityDisplayControl.editing) selectedTool.value = panTool;
  };

  const toggleCardOpen = () => {
    setEntityDisplayControl({ open: !(entityDisplayControl.open ?? false) });
  };
</script>

<!-- ─── Entity Card Root ─────────────────────────────────────────────────────── -->
<Card.Root
  class={cn(
    "shadow-none rounded-2xl border border-border/60 overflow-hidden transition-all duration-200 bg-card/90",
    highlightState === "self"
      ? "ring-1 ring-primary/25 bg-primary/[0.04]"
      : "hover:bg-accent/40 hover:border-border",
  )}
  style={`border-left: ${highlightState === "self" ? `3px solid ${color}` : "3px solid transparent"};`}
  id={`card-object-${entity.id}`}
  onclick={onCardClick}
>
  <!-- ─── Header ───────────────────────────────────────────────────────────── -->
  <Card.Header class="p-2.5 flex-col space-y-1.5">
    <div class="flex items-start justify-between gap-2">
      <!-- Left: Thumbnail + Entity ID + Summary pills -->
      <div class="flex-[1_1_auto] flex items-start overflow-hidden min-w-0 gap-2">
        <!-- Thumbnail: Image crop / Typographic fallback / Colored dot -->
        {#if thumbnails.length > 0}
          {@const thumb = thumbnails[0]}
          {@const innerSize = 36}
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
            type="button"
            class="flex-shrink-0 flex items-center justify-center rounded-lg overflow-hidden transition-all duration-200 hover:ring-2 hover:ring-primary/30"
            style="width: 40px; height: 40px; border: 2px solid {color}; background: hsl(var(--muted) / 0.8);"
            title="Highlight entity"
            onclick={onColoredDotClick}
          >
            <div class="relative overflow-hidden" style="width: {fitW}px; height: {fitH}px;">
              <img
                src="/{thumb.uri}"
                alt=""
                class="absolute max-w-none"
                style="width: {imgW}px; height: {imgH}px; left: {offX}px; top: {offY}px;"
              />
            </div>
          </button>
        {:else if hasOnlyTextSpans}
          <!-- Typographic fallback thumbnail for text-only entities -->
          <button
            type="button"
            class="flex-shrink-0 flex items-center justify-center rounded-lg transition-all duration-200 hover:ring-2 hover:ring-primary/30"
            style="width: 40px; height: 40px; border: 2px solid {color}; background: color-mix(in srgb, {color} 12%, transparent);"
            title="Highlight entity (text entity)"
            onclick={onColoredDotClick}
          >
            <TextT weight="bold" class="h-5 w-5" style="color: {color}" />
          </button>
        {:else}
          <!-- Minimal colored dot fallback -->
          <button
            type="button"
            class="rounded-full w-3 h-3 mx-1 mt-1 flex-shrink-0 ring-2 ring-card shadow-sm transition-transform hover:scale-125"
            style="background:{color}"
            title="Highlight entity"
            onclick={onColoredDotClick}
          ></button>
        {/if}

        <!-- Entity ID + annotation summary pills -->
        <button type="button" class="min-w-0 text-left flex flex-col gap-1" onclick={onColoredDotClick} title="Highlight entity">
          <span
            class={cn("block truncate text-[13px] font-semibold leading-tight transition-colors font-mono", {
              "text-foreground": highlightState !== "none",
              "text-muted-foreground":
                highlightState === "none" && selectedTool.value?.type === ToolType.Fusion,
            })}
            title={entity.id}
          >
            {entity.id}
          </span>

          <!-- Annotation type summary pills -->
          {#if Object.keys(annotationTypeSummary).length > 0}
            <div class="flex flex-wrap gap-1">
              {#each Object.entries(annotationTypeSummary) as [schema, count]}
                {@const meta = TYPE_META[schema]}
                {#if meta}
                  <span class={cn("inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium leading-none", meta.color)}>
                    {#if schema === BaseSchema.BBox}
                      <Square class="h-2.5 w-2.5" />
                    {:else if schema === BaseSchema.Mask}
                      <Ghost weight="regular" class="h-2.5 w-2.5" />
                    {:else if schema === BaseSchema.Keypoints}
                      <img src={keypointsIcon} alt="" class="h-2.5 w-2.5" />
                    {:else if schema === BaseSchema.TextSpan}
                      <TextT weight="regular" class="h-2.5 w-2.5" />
                    {:else if schema === BaseSchema.MultiPath}
                      <LineSegments weight="regular" class="h-2.5 w-2.5" />
                    {:else if schema === BaseSchema.Tracklet}
                      <GitCommit weight="regular" class="h-2.5 w-2.5" />
                    {/if}
                    {count}
                  </span>
                {/if}
              {/each}
            </div>
          {/if}
        </button>
      </div>

      <!-- Right: Action buttons -->
      <div class="flex-shrink-0 flex items-center justify-end gap-1">
        <IconButton
          onclick={() => handleSetDisplayControl("hidden", isVisible)}
          tooltipContent={isVisible ? "Hide entity" : "Show entity"}
          class="h-7 w-7 rounded-md"
        >
          {#if isVisible}
            <Eye class="h-3.5 w-3.5" />
          {:else}
            <EyeClosed weight="regular" class="h-3.5 w-3.5" />
          {/if}
        </IconButton>

        {#if entityHasTracklets(entity)}
          <IconButton
            tooltipContent={hiddenTrack ? "Show track" : "Hide track"}
            onclick={onTrackVisClick}
            class="h-7 w-7 rounded-md"
          >
            {#if hiddenTrack}<ListPlus class="h-3.5 w-3.5" />{:else}<ListDashes weight="regular" class="h-3.5 w-3.5" />{/if}
          </IconButton>
        {/if}

        {#if selectedTool.value?.type !== ToolType.Fusion}
          <IconButton
            tooltipContent={entityDisplayControl.editing ? "Stop editing" : "Edit attributes"}
            selected={entityDisplayControl.editing}
            onclick={() => onEditIconClick()}
            class="h-7 w-7 rounded-md"
          >
            <Pencil class="h-3.5 w-3.5" />
          </IconButton>
        {/if}

        <IconButton
          tooltipContent="Delete entity"
          redconfirm
          onclick={() => deleteEntity(entity)}
          class="h-7 w-7 rounded-md text-muted-foreground hover:text-destructive"
        >
          <Trash weight="regular" class="h-3.5 w-3.5" />
        </IconButton>

        <IconButton
          onclick={toggleCardOpen}
          tooltipContent={entityDisplayControl.open ? "Collapse" : "Expand"}
          class="h-7 w-7 rounded-md"
        >
          <CaretRight
            weight="regular"
            class={cn("h-3.5 w-3.5 transition-transform duration-200", {
              "rotate-90": entityDisplayControl.open,
            })}
          />
        </IconButton>
      </div>
    </div>
  </Card.Header>

  <!-- ─── Expanded Content (with slide transition) ─────────────────────────── -->
  {#if entityDisplayControl.open}
    <div transition:slide={{ duration: 200, easing: cubicOut }}>
      <Card.Content class="p-3 bg-muted/35 border-t border-border/40 space-y-3">
        <!-- Tab switcher -->
        <div class="inline-flex rounded-lg border border-border/50 bg-background/70 p-0.5">
          <button
            type="button"
            onclick={() => (detailsTab = "attributes")}
            class={cn(
              "h-7 px-2.5 rounded-md text-[11px] font-semibold tracking-wide transition-colors",
              detailsTab === "attributes"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            Attributes
          </button>
          <button
            type="button"
            onclick={() => (detailsTab = "annotations")}
            class={cn(
              "h-7 px-2.5 rounded-md text-[11px] font-semibold tracking-wide transition-colors",
              detailsTab === "annotations"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            Annotations ({totalAllowableChildCount})
          </button>
        </div>

        <!-- Attributes tab: entity-only features -->
        {#if detailsTab === "attributes"}
          <div class="space-y-2.5 animate-in fade-in duration-200">
            <!-- Entity ID reference -->
            <div class="flex items-center gap-2 px-1">
              <span class="text-[10px] text-muted-foreground/60 font-medium uppercase tracking-wider">ID</span>
              <span class="text-[11px] font-mono text-foreground/70 truncate select-all" title={entity.id}>
                {entity.id}
              </span>
            </div>

            {#if entityFeatures.length > 0}
              <div class="rounded-lg border border-border/30 bg-background/60 overflow-hidden">
                <UpdateFeatureInputs
                  featureClass="objects"
                  features={entityFeatures}
                  isEditing={entityDisplayControl.editing ?? false}
                  {saveInputChange}
                />
              </div>
            {:else}
              <div class="rounded-lg border border-dashed border-border/30 bg-muted/20 px-3 py-4 flex flex-col items-center gap-1">
                <span class="text-[11px] text-muted-foreground/50">
                  No custom attributes defined.
                </span>
              </div>
            {/if}
          </div>

        <!-- Annotations tab -->
        {:else}
          <div class="space-y-2 animate-in fade-in duration-200">
            {#if entity.ui.childs?.some((ann) => ann.ui.datasetItemType === WorkspaceType.VIDEO)}
              <p class="text-[11px] text-center text-muted-foreground/80 py-1 bg-muted/30 rounded-md">
                {allowedChilds.length > 0 ? allowedChilds.length : "No"}
                annotation{allowedChilds.length === 1 ? "" : "s"}
                on frame {currentFrameIndex.value}
              </p>
            {/if}

            {#if allowedChilds.length === 0}
              <div class="rounded-md border border-border/40 bg-background/60 px-2.5 py-2 text-xs text-muted-foreground">
                No annotations currently visible for this entity.
              </div>
            {:else}
              <div class="space-y-1.5">
                {#each allowedChilds as child (child.id)}
                  {@const childFeats = annotationFeaturesMap.get(child.id)}
                  <ChildCard
                    {entity}
                    {child}
                    {handleSetDisplayControl}
                    {onEditIconClick}
                    features={childFeats?.annFeats ?? []}
                    subEntityFeatures={childFeats?.subEntityFeats ?? []}
                    isEditing={entityDisplayControl.editing ?? false}
                    {saveInputChange}
                  />
                {/each}
              </div>
            {/if}
          </div>
        {/if}
      </Card.Content>
    </div>
  {/if}
</Card.Root>
