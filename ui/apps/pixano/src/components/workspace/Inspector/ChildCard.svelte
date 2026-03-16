<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  /* eslint-disable svelte/no-at-html-tags */

  import { slide } from "svelte/transition";
  import { cubicOut } from "svelte/easing";
  import {
    CaretRight,
    Eye,
    EyeClosed,
    Ghost,
    GitCommit,
    LineSegments,
    Link,
    Pencil,
    Quotes,
    Square,
    TextT,
    Trash,
    User,
    Robot,
    Target,
  } from "phosphor-svelte";

  import { ToolType } from "$lib/tools";
  import { Button } from "bits-ui";

  import {
    Annotation,
    BaseSchema,
    BBox,
    Entity,
    IconButton,
    Item,
    Keypoints,
    Mask,
    TextSpan,
    Tracklet,
    type DisplayControl,
    type KeypointAnnotation,
  } from "$lib/ui";
  import type { Feature } from "$lib/types/workspace";
  import { cn } from "$lib/utils/styleUtils";
  import { keypointsIcon } from "$lib/assets";

  import UpdateFeatureInputs from "../Features/UpdateFeatureInputs.svelte";
  import { deleteEntity, onDeleteTrackItemClick } from "$lib/utils/entityDeletion";
  import { relink } from "$lib/utils/entityRelink";
  import { getWorkspaceContext } from "$lib/workspace/context";
  import {
    annotations,
    current_itemBBoxes,
    current_itemKeypoints,
    current_itemMasks,
    interpolate,
    mediaViews,
    selectedTool,
  } from "$lib/stores/workspaceStores.svelte";
  import RelinkAnnotation from "../SaveShape/RelinkAnnotation.svelte";

  // ─── Type labels & icons mapping ──────────────────────────────────────────
  const TYPE_LABELS: Record<string, string> = {
    [BaseSchema.BBox]: "Bounding Box",
    [BaseSchema.Mask]: "Segmentation Mask",
    [BaseSchema.MultiPath]: "Multi-Path",
    [BaseSchema.Keypoints]: "Keypoints",
    [BaseSchema.TextSpan]: "Text Span",
    [BaseSchema.Tracklet]: "Track",
  };

  // ─── Source name color coding ─────────────────────────────────────────────
  function getSourceStyle(sourceName: string): { class: string; icon: typeof User } {
    switch (sourceName) {
      case "Pixano":
        return { class: "bg-blue-500/10 text-blue-400 border-blue-500/20", icon: User };
      case "Pre-annotation":
        return { class: "bg-amber-500/10 text-amber-400 border-amber-500/20", icon: Robot };
      case "Ground Truth":
        return { class: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20", icon: Target };
      default:
        return { class: "bg-muted text-muted-foreground border-border/50", icon: Robot };
    }
  }

  // ─── Confidence color coding ──────────────────────────────────────────────
  function getConfidenceStyle(confidence: number): string {
    if (confidence >= 0.8) return "bg-emerald-500/15 text-emerald-400";
    if (confidence >= 0.5) return "bg-amber-500/15 text-amber-400";
    return "bg-red-500/15 text-red-400";
  }

  // ─── Props ────────────────────────────────────────────────────────────────
  interface Props {
    entity: Entity;
    child: Annotation;
    features?: Feature[];
    subEntityFeatures?: Feature[];
    isEditing?: boolean;
    saveInputChange?: (
      value: string | boolean | number,
      propertyName: string,
      obj: Item | Entity | Annotation,
    ) => void;
    handleSetDisplayControl: (
      displayControlProperty: keyof DisplayControl,
      new_value: boolean,
      child: Annotation | null,
    ) => void;
    onEditIconClick: (child: Annotation | null) => void;
  }

  let {
    entity,
    child,
    features = [],
    subEntityFeatures = [],
    isEditing = false,
    saveInputChange = () => {},
    handleSetDisplayControl,
    onEditIconClick,
  }: Props = $props();

  let showRelink = $state(false);
  let showDetails = $state(true);
  let selectedEntityId: string = $state("new");
  let mustMerge: boolean = $state(false);
  let overlapTargetId: string = $state("");
  const { manifest } = getWorkspaceContext();

  // ─── Derived state ────────────────────────────────────────────────────────
  const childEditing = $derived.by(() => {
    void annotations.value;
    return child.ui.displayControl.editing;
  });

  const childVisible = $derived.by(() => {
    void annotations.value;
    return !child.ui.displayControl.hidden;
  });

  const typeLabel = $derived(TYPE_LABELS[child.table_info.base_schema] ?? child.table_info.base_schema);

  const isMultiView = Object.keys(mediaViews.value).length > 1;

  // ─── Source provenance ────────────────────────────────────────────────────
  const sourceName = $derived(
    typeof child.data.source_name === "string" && child.data.source_name !== ""
      ? child.data.source_name
      : null,
  );

  const sourceMetadataParsed = $derived.by(() => {
    const raw = child.data.source_metadata;
    if (typeof raw !== "string" || raw === "" || raw === "{}") return null;
    try {
      const parsed = JSON.parse(raw);
      if (typeof parsed === "object" && parsed !== null && Object.keys(parsed).length > 0) {
        return parsed as Record<string, unknown>;
      }
    } catch {
      // If not valid JSON, show as-is
      return { value: raw } as Record<string, unknown>;
    }
    return null;
  });

  const sourceStyle = $derived(sourceName ? getSourceStyle(sourceName) : null);

  // ─── BBox-specific derived data ───────────────────────────────────────────
  const bboxData = $derived.by(() => {
    if (!child.is_type(BaseSchema.BBox)) return null;
    const data = (child as BBox).data;
    const format = typeof data.format === "string" ? data.format : "xyxy";
    const isNormalized = typeof data.is_normalized === "boolean" ? data.is_normalized : false;
    const confidence = typeof data.confidence === "number" ? data.confidence : null;
    const coords = Array.isArray(data.coords) ? data.coords : [];

    let labels: string[];
    if (format === "xywh") {
      labels = ["x", "y", "w", "h"];
    } else if (format === "xyzxyz" || format === "xyzwhd") {
      labels = format === "xyzxyz" ? ["x1", "y1", "z1", "x2", "y2", "z2"] : ["x", "y", "z", "w", "h", "d"];
    } else {
      // default xyxy
      labels = ["x1", "y1", "x2", "y2"];
    }

    return { coords, format, isNormalized, confidence, labels };
  });

  // ─── Mask-specific derived data ───────────────────────────────────────────
  const maskData = $derived.by(() => {
    if (!child.is_type(BaseSchema.Mask)) return null;
    const data = (child as Mask).data;
    const maskUi = (child as Mask).ui;
    const size = Array.isArray(data.size) ? data.size : [];
    const bounds = maskUi.bounds ?? null;
    return { size, bounds };
  });

  // ─── TextSpan-specific derived data ───────────────────────────────────────
  const textSpanData = $derived.by(() => {
    if (!child.is_type(BaseSchema.TextSpan)) return null;
    const data = (child as TextSpan).data;
    const mention = typeof data.mention === "string" ? data.mention : "";
    const starts = Array.isArray(data.spans_start) ? data.spans_start : [];
    const ends = Array.isArray(data.spans_end) ? data.spans_end : [];
    // Zip the starts and ends into spans pairs
    const spans = starts.map((s: number, i: number) => [s, ends[i] ?? s]);
    // Gather extra display fields (role, concept, etc.)
    const extras: { key: string; value: string }[] = [];
    for (const key of ["role", "concept"] as const) {
      const val = data[key];
      if (typeof val === "string" && val !== "") {
        extras.push({ key, value: val });
      }
    }
    return { mention, spans, extras };
  });

  // ─── Keypoints-specific derived data ──────────────────────────────────────
  const keypointsData = $derived.by(() => {
    if (!child.is_type(BaseSchema.Keypoints)) return null;
    const data = (child as Keypoints).data;
    const templateId = typeof data.template_id === "string" ? data.template_id : "";
    const coords = Array.isArray(data.coords) ? data.coords : [];
    const states = Array.isArray(data.states) ? data.states as string[] : [];
    const vertexCount = Math.floor(coords.length / 2);
    const visibleCount = states.filter((s) => s === "visible").length;
    const hiddenCount = states.filter((s) => s === "hidden" || s === "invisible").length;
    return { templateId, vertexCount, visibleCount, hiddenCount };
  });

  // ─── Tracklet-specific derived data ───────────────────────────────────────
  const trackletData = $derived.by(() => {
    if (!child.is_type(BaseSchema.Tracklet)) return null;
    const data = (child as Tracklet).data;
    return {
      startFrame: data.start_frame,
      endFrame: data.end_frame,
    };
  });

  const currentTrackChilds = $derived.by(() => {
    if (!child.is_type(BaseSchema.Tracklet)) return [];
    void interpolate.value;
    const trackChilds = (child as Tracklet).ui.childs;
    const current_Anns = [
      ...current_itemBBoxes.value,
      ...current_itemKeypoints.value,
      ...current_itemMasks.value,
    ] as (BBox | KeypointAnnotation | Mask)[];

    const result: { trackChild: Annotation; interpolated: boolean }[] = [];
    current_Anns.forEach((cann) => {
      const directMatch = trackChilds.find((ann) => ann.id === cann.id);
      if (directMatch) {
        result.push({ trackChild: directMatch, interpolated: false });
      } else if (
        trackChilds.some(
          (ann) =>
            cann.ui &&
            "startRef" in cann.ui &&
            cann.ui.startRef &&
            ann.id === cann.ui.startRef.id,
        )
      ) {
        result.push({ trackChild: cann as Annotation, interpolated: true });
      }
    });
    return result;
  });

  const handleRelink = () => {
    relink(child, entity, selectedEntityId, mustMerge, overlapTargetId, manifest);
    showRelink = false;
  };

  // Format a coordinate value for display
  function fmtCoord(v: number): string {
    if (Number.isInteger(v)) return String(v);
    return v.toFixed(4);
  }

  // Format confidence as percentage
  function fmtConfidence(v: number): string {
    return `${(v * 100).toFixed(1)}%`;
  }
</script>

<!-- ═══════════════════════════════════════════════════════════════════════════ -->
<!-- CHILD ANNOTATION CARD                                                      -->
<!-- ═══════════════════════════════════════════════════════════════════════════ -->
<div
  class="rounded-lg border border-border/40 bg-background/60 overflow-hidden transition-all duration-200 hover:border-border/70 hover:shadow-sm group/child"
>
  <!-- ─── Header row: type icon + label + view_name + actions ──────────────── -->
  <div class="flex items-center justify-between px-2 py-1.5 gap-1">
    <!-- Left: visibility + type icon + label -->
    <div class="flex-[1_1_auto] flex items-center overflow-hidden min-w-0 gap-1">
      <IconButton
        onclick={() => handleSetDisplayControl("hidden", childVisible, child)}
        tooltipContent={childVisible ? "Hide" : "Show"}
        class="h-6 w-6 opacity-60 hover:opacity-100"
      >
        {#if childVisible}
          <Eye class="h-3 w-3" />
        {:else}
          <EyeClosed weight="regular" class="h-3 w-3" />
        {/if}
      </IconButton>

      <!-- Type icon -->
      <div class="flex items-center text-muted-foreground/70 flex-shrink-0">
        {#if child.is_type(BaseSchema.BBox)}
          <Square class="h-3.5 w-3.5" />
        {:else if child.is_type(BaseSchema.Mask)}
          <Ghost weight="regular" class="h-3.5 w-3.5" />
        {:else if child.is_type(BaseSchema.Keypoints)}
          <img src={keypointsIcon} alt="keypoints" class="h-3.5 w-3.5 opacity-70" />
        {:else if child.is_type(BaseSchema.MultiPath)}
          <LineSegments weight="regular" class="h-3.5 w-3.5" />
        {:else if child.is_type(BaseSchema.Tracklet)}
          <GitCommit weight="regular" class="h-3.5 w-3.5" />
        {:else if child.is_type(BaseSchema.TextSpan)}
          <TextT weight="regular" class="h-3.5 w-3.5" />
        {/if}
      </div>

      <!-- Type label -->
      <span class="text-[11px] font-semibold text-foreground/80 truncate">
        {typeLabel}
      </span>

      <!-- View name pill (multi-view only) -->
      {#if isMultiView && child.data.view_name}
        <span class="flex-shrink-0 px-1.5 py-0.5 rounded bg-muted/60 text-[9px] font-medium text-muted-foreground leading-none">
          {child.data.view_name}
        </span>
      {/if}
    </div>

    <!-- Right: action buttons (visible on hover) + detail toggle -->
    <div class="flex-shrink-0 flex items-center gap-0.5">
      <div class="flex items-center gap-0.5 opacity-0 group-hover/child:opacity-100 transition-opacity duration-200">
        {#if selectedTool.value?.type !== ToolType.Fusion}
          {#if !(child.is_type(BaseSchema.TextSpan) || child.is_type(BaseSchema.Tracklet))}
            <IconButton
              tooltipContent="Edit object"
              selected={childEditing}
              onclick={() => onEditIconClick(child)}
              class="h-6 w-6"
            >
              <Pencil class="h-3 w-3" />
            </IconButton>
          {/if}
          <IconButton
            tooltipContent="Relink object"
            selected={showRelink}
            onclick={() => { showRelink = !showRelink; }}
            class="h-6 w-6"
          >
            <Link class="h-3 w-3" />
          </IconButton>
          <IconButton
            tooltipContent="Delete object"
            redconfirm
            onclick={() => deleteEntity(entity, child)}
            class="h-6 w-6 text-muted-foreground hover:text-destructive"
          >
            <Trash weight="regular" class="h-3 w-3" />
          </IconButton>
        {/if}
      </div>

      <!-- Detail toggle chevron -->
      <button
        type="button"
        class="h-6 w-6 flex items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-accent/40 transition-colors"
        onclick={() => { showDetails = !showDetails; }}
        title={showDetails ? "Hide details" : "Show details"}
      >
        <CaretRight
          weight="regular"
          class={cn("h-3 w-3 transition-transform duration-200", { "rotate-90": showDetails })}
        />
      </button>
    </div>
  </div>

  <!-- ─── Detail block (collapsible) ───────────────────────────────────────── -->
  {#if showDetails}
    <div transition:slide={{ duration: 150, easing: cubicOut }}>
      <div class="px-2.5 pb-2 space-y-1.5">
        <!-- Source provenance line -->
        {#if sourceName}
          {@const style = sourceStyle!}
          <div class="flex items-center gap-1.5">
            <span class="text-[10px] text-muted-foreground/60">Source</span>
            <span class={cn("inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[10px] font-medium leading-none", style.class)}>
              <svelte:component this={style.icon} weight="regular" class="h-2.5 w-2.5" />
              {sourceName}
            </span>
            {#if sourceMetadataParsed}
              <span
                class="text-[9px] text-muted-foreground/50 truncate max-w-[150px] cursor-help"
                title={JSON.stringify(sourceMetadataParsed, null, 2)}
              >
                {Object.entries(sourceMetadataParsed).map(([k, v]) => `${k}: ${v}`).join(", ")}
              </span>
            {/if}
          </div>
        {/if}

        <!-- ═══════════════════════════════════════════════════════════════ -->
        <!-- TYPE-SPECIFIC VISUALIZATIONS                                    -->
        <!-- ═══════════════════════════════════════════════════════════════ -->

        <!-- ─── BBox ─────────────────────────────────────────────────────── -->
        {#if bboxData}
          <div class="rounded-md bg-muted/30 border border-border/30 p-2 space-y-1.5">
            <!-- Coordinate grid -->
            <div class="grid grid-cols-2 gap-x-3 gap-y-0.5">
              {#each bboxData.labels as label, i}
                {#if i < bboxData.coords.length}
                  <div class="flex items-center justify-between">
                    <span class="text-[10px] text-muted-foreground/70 font-medium">{label}</span>
                    <span class="text-[11px] font-mono text-foreground/90">{fmtCoord(bboxData.coords[i])}</span>
                  </div>
                {/if}
              {/each}
            </div>

            <!-- Format row -->
            <div class="flex items-center gap-2 pt-0.5">
              <span class="px-1.5 py-0.5 rounded bg-muted/50 text-[10px] font-mono text-muted-foreground leading-none">
                {bboxData.format}
              </span>
              {#if bboxData.isNormalized}
                <span class="px-1 py-0.5 rounded bg-muted/50 text-[9px] font-medium text-muted-foreground/60 leading-none" title="Coordinates are normalized">
                  norm
                </span>
              {/if}
            </div>
          </div>

        <!-- ─── Mask / CompressedRLE ─────────────────────────────────────── -->
        {:else if maskData}
          <div class="rounded-md bg-muted/30 border border-border/30 p-2 space-y-1">
            {#if maskData.size.length >= 2}
              <div class="flex items-center gap-2">
                <span class="text-[10px] text-muted-foreground/70 font-medium">Size</span>
                <span class="text-[11px] font-mono text-foreground/90">
                  {maskData.size[0]} &times; {maskData.size[1]}
                </span>
              </div>
            {/if}
            {#if maskData.bounds}
              <div class="flex items-center gap-2">
                <span class="text-[10px] text-muted-foreground/70 font-medium">Bounds</span>
                <span class="text-[11px] font-mono text-foreground/80">
                  {Math.round(maskData.bounds.x)}, {Math.round(maskData.bounds.y)} &mdash; {Math.round(maskData.bounds.width)}&times;{Math.round(maskData.bounds.height)}
                </span>
              </div>
            {/if}
          </div>

        <!-- ─── TextSpan ─────────────────────────────────────────────────── -->
        {:else if textSpanData}
          <div class="rounded-md bg-muted/30 border border-border/30 p-2 space-y-1.5">
            <!-- Mention as a styled quote -->
            {#if textSpanData.mention}
              <div class="flex items-start gap-1.5">
                <Quotes weight="fill" class="h-3 w-3 text-muted-foreground/40 flex-shrink-0 mt-0.5" />
                <span class="text-[11px] italic text-foreground/90 leading-snug break-words">
                  {textSpanData.mention}
                </span>
              </div>
            {/if}

            <!-- Span offsets -->
            {#if textSpanData.spans.length > 0}
              <div class="flex items-center gap-2 flex-wrap">
                <span class="text-[10px] text-muted-foreground/70 font-medium">Spans</span>
                {#each textSpanData.spans as span}
                  <span class="px-1.5 py-0.5 rounded bg-muted/50 text-[10px] font-mono text-muted-foreground leading-none">
                    [{span[0]}, {span[1]}]
                  </span>
                {/each}
              </div>
            {/if}

            <!-- Extra fields (role, concept, etc.) -->
            {#if textSpanData.extras.length > 0}
              <div class="flex items-center gap-1.5 flex-wrap">
                {#each textSpanData.extras as extra}
                  <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-accent/30 text-[10px] font-medium text-foreground/70 leading-none">
                    <span class="text-muted-foreground/60">{extra.key}:</span>
                    {extra.value}
                  </span>
                {/each}
              </div>
            {/if}
          </div>

        <!-- ─── Keypoints ────────────────────────────────────────────────── -->
        {:else if keypointsData}
          <div class="rounded-md bg-muted/30 border border-border/30 p-2 space-y-1">
            {#if keypointsData.templateId}
              <div class="flex items-center gap-2">
                <span class="text-[10px] text-muted-foreground/70 font-medium">Template</span>
                <span class="text-[11px] font-mono text-foreground/80">{keypointsData.templateId}</span>
              </div>
            {/if}
            <div class="flex items-center gap-2">
              <span class="text-[10px] text-muted-foreground/70 font-medium">Vertices</span>
              <span class="text-[11px] text-foreground/80">{keypointsData.vertexCount}</span>
              {#if keypointsData.visibleCount > 0 || keypointsData.hiddenCount > 0}
                <span class="text-[9px] text-muted-foreground/50">
                  ({keypointsData.visibleCount} visible, {keypointsData.hiddenCount} hidden)
                </span>
              {/if}
            </div>
          </div>

        <!-- ─── Tracklet ─────────────────────────────────────────────────── -->
        {:else if trackletData}
          <div class="rounded-md bg-muted/30 border border-border/30 p-2">
            <div class="flex items-center gap-2">
              <span class="text-[10px] text-muted-foreground/70 font-medium">Frames</span>
              <span class="text-[11px] font-mono text-foreground/80">
                {trackletData.startFrame}
              </span>
              <span class="text-[10px] text-muted-foreground/40">&rarr;</span>
              <span class="text-[11px] font-mono text-foreground/80">
                {trackletData.endFrame}
              </span>
              <span class="text-[9px] text-muted-foreground/50">
                ({trackletData.endFrame - trackletData.startFrame + 1} frames)
              </span>
            </div>
          </div>
        {/if}

        <!-- ═══════════════════════════════════════════════════════════════ -->
        <!-- CUSTOM ATTRIBUTES (from annotation + sub-entity features)       -->
        <!-- ═══════════════════════════════════════════════════════════════ -->

        <!-- Sub-entity attributes (when annotation belongs to a sub-entity) -->
        {#if subEntityFeatures.length > 0}
          <div class="border-t border-border/20 pt-1.5 mt-1 space-y-0.5">
            <span class="text-[10px] text-muted-foreground/50 font-medium uppercase tracking-wider">Entity attributes</span>
            <UpdateFeatureInputs
              featureClass="objects"
              features={subEntityFeatures}
              {isEditing}
              {saveInputChange}
            />
          </div>
        {/if}

        <!-- Annotation's own custom attributes + confidence -->
        {#if features.length > 0 || bboxData?.confidence !== null && bboxData?.confidence !== undefined}
          <div class="border-t border-border/20 pt-1.5 mt-1 space-y-0.5">
            <span class="text-[10px] text-muted-foreground/50 font-medium uppercase tracking-wider">Attributes</span>
            {#if bboxData?.confidence !== null && bboxData?.confidence !== undefined}
              <div class="flex w-full items-center justify-between py-1.5 px-2 rounded-md hover:bg-accent/50 transition-colors duration-100 min-h-[32px]">
                <span class="text-[13px] text-muted-foreground truncate max-w-[45%]">confidence</span>
                <span class={cn("inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold leading-none", getConfidenceStyle(bboxData.confidence))}>
                  {fmtConfidence(bboxData.confidence)}
                </span>
              </div>
            {/if}
            {#if features.length > 0}
              <UpdateFeatureInputs
                featureClass="objects"
                {features}
                {isEditing}
                {saveInputChange}
              />
            {/if}
          </div>
        {/if}
      </div>
    </div>
  {/if}

  <!-- ─── Relink panel ─────────────────────────────────────────────────────── -->
  {#if showRelink}
    <div transition:slide={{ duration: 150, easing: cubicOut }}>
      <div class="flex flex-row gap-4 items-center px-2.5 pb-2">
        <RelinkAnnotation
          bind:selectedEntityId
          bind:mustMerge
          bind:overlapTargetId
          baseSchema={child.table_info.base_schema}
          viewRef={{ name: child.data.view_name, id: child.data.frame_id as string }}
          track={child}
        />
        <Button.Root
          type="button"
          class={cn(
            "inline-flex items-center justify-center rounded-lg text-sm font-medium whitespace-nowrap ring-offset-background transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 h-10 px-4 py-2 mt-4",
          )}
          onclick={handleRelink}
        >
          OK
        </Button.Root>
      </div>
    </div>
  {/if}
</div>

<!-- ─── Tracklet nested per-frame children ─────────────────────────────────── -->
{#if child.is_type(BaseSchema.Tracklet) && currentTrackChilds.length > 0}
  <div class="ml-3 pl-3 border-l-2 border-border/30 space-y-0.5 mt-0.5">
    <!-- NOTE: trackChild may be a clone (from interpolation), not a real Annotation, so we can't use is_type -->
    {#each currentTrackChilds as { trackChild, interpolated }}
      {@const displayName = interpolated
        ? `<i class="text-muted-foreground/50">interpolated</i> (${trackChild.id})`
        : trackChild.id}
      <div class="flex items-center justify-between w-full overflow-hidden py-0.5 px-1 rounded hover:bg-muted/30 transition-colors group/trackchild">
        <div class="flex items-center flex-1 min-w-0 overflow-hidden gap-1">
          <div class="flex items-center text-muted-foreground/60 flex-shrink-0">
            {#if trackChild.table_info.base_schema === BaseSchema.BBox}
              <Square class="h-3.5 w-3.5" />
            {:else if trackChild.table_info.base_schema === BaseSchema.Mask}
              <Ghost weight="regular" class="h-3.5 w-3.5" />
            {:else if trackChild.table_info.base_schema === BaseSchema.Keypoints}
              <img src={keypointsIcon} alt="keypoints" class="h-3.5 w-3.5 opacity-60" />
            {:else if trackChild.table_info.base_schema === BaseSchema.TextSpan}
              <TextT weight="regular" class="h-3.5 w-3.5" />
            {/if}
          </div>
          <span class="block truncate text-[11px] text-foreground/70" title={trackChild.id}>
            {@html displayName}
          </span>
        </div>
        {#if selectedTool.value?.type !== ToolType.Fusion && !interpolated}
          <div class="flex items-center gap-0.5 opacity-0 group-hover/trackchild:opacity-100 transition-opacity duration-200">
            {#if [BaseSchema.BBox, BaseSchema.Mask, BaseSchema.Keypoints].includes(trackChild.table_info.base_schema)}
              <IconButton
                tooltipContent="Edit object"
                selected={trackChild.ui.displayControl.editing}
                onclick={() => onEditIconClick(trackChild)}
                class="h-6 w-6"
              >
                <Pencil class="h-3 w-3" />
              </IconButton>
            {/if}
            <IconButton
              tooltipContent="Delete object"
              redconfirm
              onclick={() => onDeleteTrackItemClick(child, trackChild.ui.frame_index, trackChild)}
              class="h-6 w-6 text-muted-foreground hover:text-destructive"
            >
              <Trash weight="regular" class="h-3 w-3" />
            </IconButton>
          </div>
        {/if}
      </div>
    {/each}
  </div>
{/if}
