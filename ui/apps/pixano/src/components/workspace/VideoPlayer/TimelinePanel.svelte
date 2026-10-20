<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // The video timeline: the player bar, then one scroller holding a sticky ruler, a sticky
  // column of row headers and the lanes. Every lane shares one frame↔x mapping; the panel
  // measures it, decides which part of the lanes to draw, and handles every pointer on the
  // lanes itself (ticks, scrubbing, drag to retime, hover, the track menu), from the rows'
  // models rather than from the DOM.
  import { ContextMenu } from "bits-ui";
  import { onDestroy, tick, untrack } from "svelte";

  import DetectionTracksTimelineRows from "./DetectionTracksTimelineRows.svelte";
  import EntityTimelineRow from "./EntityTimelineRow.svelte";
  import TimelineCommandBar from "./TimelineCommandBar.svelte";
  import {
    setTimelineLayoutContext,
    type OverlayMark,
    type OverlayTooltip,
    type TimelineMenuTarget,
  } from "./timelineContext";
  import TimelineDensityStrip from "./TimelineDensityStrip.svelte";
  import TimelineOverlays from "./TimelineOverlays.svelte";
  import TimelineRuler from "./TimelineRuler.svelte";
  import TimelineTrackMenu from "./TimelineTrackMenu.svelte";
  import TrackingTimelineRow from "./TrackingTimelineRow.svelte";
  import {
    timelineCandidateIds,
    timelineNavLane,
    timelineRows,
    timelineSelectedRowId,
    timelineTopEntityIds,
    timelineTrackedCount,
    timelineTrackModels,
    togglePinnedTimelineEntity,
    toggleTimelinePinnedOnly,
  } from "$lib/stores/timelineInspectorStore.svelte";
  import { trackletIdOfShape } from "$lib/stores/trackEditing";
  import {
    detectionTimelineLanes,
    selectDetectionTrack,
  } from "$lib/stores/trackingByDetectionStore.svelte";
  import { activeTrackingTimelineState } from "$lib/stores/trackingStore.svelte";
  import {
    currentFrameIndex,
    currentItemId,
    lastFrameIndex,
    playbackState,
    timelineFps,
    timelineZoom,
    videoFps,
  } from "$lib/stores/videoStores.svelte";
  import {
    annotationColors,
    current_itemBBoxes,
    current_itemKeypoints,
    editedTrackletId,
    entities,
    selectedTool,
    trackletIdByChildId,
    tracks,
  } from "$lib/stores/workspaceStores.svelte";
  import { keyframeColorAt, keyframeIndexAt, tracksCoveringFrame } from "$lib/timeline/laneQueries";
  import { formatTimecode, frameTime } from "$lib/timeline/timeFormat";
  import {
    anchoredScrollLeft,
    createTimelineGeometry,
    frameToX,
    frameWindowOf,
    horizontalRenderWindow,
    horizontalWindowIndex,
    laneWidthForZoom,
    revealScrollLeft,
    TIMELINE_HEADER_WIDTH,
    xToFrame,
    zoomAnchorFrame,
  } from "$lib/timeline/timelineGeometry";
  import { hitTestLane, type LaneHit } from "$lib/timeline/timelineHitTest";
  import {
    formatTickTooltip,
    pressKeyframe,
    reduceKeyframeDrag,
    type DragState,
  } from "$lib/timeline/timelineInteraction";
  import {
    buildTimelineLayout,
    fillerHeight,
    revealScrollTop,
    slotAtY,
    slotInRange,
    verticalRenderRange,
    verticalWindowIndex,
    type Slot,
    type SlotInput,
  } from "$lib/timeline/timelineLayout";
  import {
    cornerLabel,
    fusionHighlightState,
    isHiddenInInspector,
    rowGraphicsOpacity,
    TIMELINE_EMPTY_TEXT,
    timelineEmptyState,
  } from "$lib/timeline/timelineRows";
  import { MARKS_ENTITY, type EntityTrackModel } from "$lib/timeline/types";
  import { ToolType } from "$lib/tools";
  import type { Tracklet } from "$lib/types/dataset";
  import { editModeBlockedReason, editTrack, exitEditMode } from "$lib/utils/editMode";
  import { clearHighlighting } from "$lib/utils/highlightOperations";
  import { handleMenuKeydown } from "$lib/utils/menuKeys";
  import {
    activateTimelineRow,
    currentTimelinePolicy,
    leaveDrawingTool,
    seekTimeline,
    selectTimelineKeyframe,
  } from "$lib/utils/timelineActions";
  import { TIMELINE_ZOOM_MIN, timelineZoomMax } from "$lib/utils/timelineZoom";
  import { keyframeRetimeBoundsFor, retimeKeyframe } from "$lib/utils/trackletOperations";

  /** The sticky band above the rows: the 44 px ruler and the 4 px density strip. */
  const RULER_BAND_HEIGHT = 48;

  // ─── Measurements and windows ─────────────────────────────────────────────

  let scroller = $state<HTMLDivElement>();
  let body = $state<HTMLDivElement>();
  let clientWidth = $state(0);
  let clientHeight = $state(0);
  let scrollLeft = $state(0);
  let scrollTop = $state(0);
  let dpr = $state(typeof window === "undefined" ? 1 : window.devicePixelRatio || 1);

  const viewportWidth = $derived(Math.max(0, clientWidth - TIMELINE_HEADER_WIDTH));
  const bodyViewportHeight = $derived(Math.max(0, clientHeight - RULER_BAND_HEIGHT));
  const zoom = $derived(timelineZoom.value[0] ?? TIMELINE_ZOOM_MIN);
  const zoomMax = $derived(timelineZoomMax(lastFrameIndex.value));
  const laneWidth = $derived(laneWidthForZoom(viewportWidth, zoom));
  const geometry = $derived(createTimelineGeometry(lastFrameIndex.value, laneWidth));
  const windowIndexX = $derived(horizontalWindowIndex(scrollLeft, viewportWidth));
  const pxWindow = $derived(horizontalRenderWindow(windowIndexX, viewportWidth, laneWidth));
  const frameWindow = $derived(frameWindowOf(geometry, pxWindow));
  const windowIndexY = $derived(verticalWindowIndex(scrollTop, bodyViewportHeight));
  const yRange = $derived(verticalRenderRange(windowIndexY, bodyViewportHeight));
  const fps = $derived(timelineFps.value);

  setTimelineLayoutContext({
    get geometry() {
      return geometry;
    },
    get pxWindow() {
      return pxWindow;
    },
    get frameWindow() {
      return frameWindow;
    },
    get dpr() {
      return dpr;
    },
    get fps() {
      return fps;
    },
  });

  // ─── Rows ─────────────────────────────────────────────────────────────────

  const rowList = $derived(timelineRows.value);
  const models = $derived(timelineTrackModels.value);
  const entitiesById = $derived(new Map(entities.value.map((entity) => [entity.id, entity])));
  const topIds = $derived(timelineTopEntityIds.value);
  const selectedRowId = $derived(timelineSelectedRowId.value);
  const sessionState = $derived(activeTrackingTimelineState.value);
  const detectionLanes = $derived(detectionTimelineLanes.value);
  const selectedToolType = $derived(selectedTool.value?.type ?? ToolType.Pan);

  const layout = $derived(
    buildTimelineLayout([
      ...(sessionState ? [{ key: "session", kind: "session" } satisfies SlotInput] : []),
      ...detectionLanes.map(
        (lane): SlotInput => ({ key: `detection:${lane.trackId}`, kind: "detection" }),
      ),
      ...rowList.ids.map((id): SlotInput => ({ key: id, kind: "entity" })),
    ]),
  );
  const bodyHeight = $derived(layout.height + fillerHeight(layout, bodyViewportHeight));
  const sessionHeight = $derived(layout.slots.find((slot) => slot.kind === "session")?.height ?? 0);
  const detectionHeight = $derived(
    layout.slots.find((slot) => slot.kind === "detection")?.height ?? 0,
  );
  const emptyState = $derived(
    rowList.ids.length > 0
      ? null
      : timelineEmptyState({
          trackedCount: timelineTrackedCount.value,
          visibleCount: rowList.candidateCount,
        }),
  );
  const corner = $derived(cornerLabel(videoFps.value, (lastFrameIndex.value ?? 0) + 1));

  const densitySpans = $derived(
    timelineCandidateIds.value.flatMap((id) => models.get(id)?.union.spans ?? []),
  );

  // Dimmed graphics: an object hidden in the inspector, or left out of a fusion.
  const rowGraphics = $derived.by(() => {
    const fusion = selectedToolType === ToolType.Fusion;
    const ownTracks = new Map<string, Tracklet[]>();
    for (const tracklet of tracks.value) {
      const entityId = tracklet.data.entity_id;
      if (!entityId) continue;
      const list = ownTracks.get(entityId);
      if (list) list.push(tracklet);
      else ownTracks.set(entityId, [tracklet]);
    }
    const opacity = new Map<string, number>();
    for (const [entityId, own] of ownTracks) {
      opacity.set(
        entityId,
        rowGraphicsOpacity({
          hiddenInInspector: isHiddenInInspector(own),
          fusionDimmed: fusion && fusionHighlightState(own) === "none",
        }),
      );
    }
    return opacity;
  });

  // The pencil: the row's track with a box or keypoints on the current frame.
  const trackIdsWithShapeHere = $derived.by(() => {
    const ids = new Set<string>();
    const byChild = trackletIdByChildId.value;
    for (const shape of [...current_itemBBoxes.value, ...current_itemKeypoints.value]) {
      const trackletId = trackletIdOfShape(shape, byChild);
      if (trackletId !== undefined) ids.add(trackletId);
    }
    return ids;
  });
  const editingRowId = $derived.by(() => {
    const trackletId = editedTrackletId.value;
    if (!trackletId) return null;
    return tracks.value.find((tracklet) => tracklet.id === trackletId)?.data.entity_id ?? null;
  });
  const editBlockedReason = $derived(editModeBlockedReason());

  function editableTrackId(model: EntityTrackModel): string | null {
    return model.union.tracks.find((track) => trackIdsWithShapeHere.has(track.id))?.id ?? null;
  }

  function editUnavailableReason(model: EntityTrackModel): string | null {
    if (editBlockedReason) return editBlockedReason;
    return editableTrackId(model) ? null : "No box on this frame";
  }

  function onTogglePencil(rowId: string, model: EntityTrackModel) {
    if (editingRowId === rowId) {
      exitEditMode();
      return;
    }
    const trackletId = editableTrackId(model);
    if (trackletId) editTrack(trackletId, { reveal: false });
  }

  /** Where a header click brings the playhead: into the row's tracks, unless it is in them. */
  function entryFrame(model: EntityTrackModel): number | null {
    const frame = currentFrameIndex.value;
    const inside = model.union.spans.some((span) => span.start <= frame && frame <= span.end);
    return inside || !Number.isFinite(model.firstFrame) ? null : model.firstFrame;
  }

  function onSelectRow(rowId: string, model: EntityTrackModel) {
    activateTimelineRow(
      { rowId, topId: topIds.get(rowId) ?? rowId },
      { selected: selectedRowId === rowId, entryFrame: entryFrame(model) },
    );
  }

  const resetHighlight = () => {
    if (![ToolType.Pan, ToolType.Fusion].includes(selectedToolType)) clearHighlighting();
  };

  // ─── Pointer on the lanes ─────────────────────────────────────────────────

  interface KeyframeDrag {
    pointerId: number;
    rowId: string;
    ownerIds: string[];
    state: DragState;
  }

  let scrubPointerId: number | null = null;
  let scrubbing = false;
  let drag: KeyframeDrag | null = null;
  let dragPreview = $state<{ rowId: string; source: number; frame: number } | null>(null);
  let hover = $state<{ slot: Slot; hit: Extract<LaneHit, { kind: "tick" }> } | null>(null);
  let cursor = $state("");
  let pendingMove: { laneX: number; y: number } | null = null;
  let moveRequest = 0;
  let scrollRequest = 0;

  function bodyPoint(event: MouseEvent): { laneX: number; y: number } {
    const rect = body?.getBoundingClientRect();
    if (!rect) return { laneX: 0, y: 0 };
    return {
      laneX: event.clientX - rect.left - TIMELINE_HEADER_WIDTH,
      y: event.clientY - rect.top,
    };
  }

  function isOnHeader(event: Event): boolean {
    return (
      event.target instanceof Element && event.target.closest("[data-timeline-header]") !== null
    );
  }

  function entitySlotAt(y: number): Slot | null {
    const slot = layout.slots[slotAtY(layout, y)];
    return slot?.kind === "entity" ? slot : null;
  }

  function startScrub(event: PointerEvent, laneX: number) {
    scrubPointerId = event.pointerId;
    scrubbing = true;
    body?.setPointerCapture(event.pointerId);
    seekTimeline(xToFrame(geometry, laneX));
  }

  function onBodyPointerDown(event: PointerEvent) {
    if (event.button !== 0 || event.ctrlKey || isOnHeader(event)) return;
    const point = bodyPoint(event);
    const slot = entitySlotAt(point.y);
    const model = slot ? models.get(slot.key) : undefined;
    hover = null;
    if (slot && model) {
      const hit = hitTestLane(model.union, geometry, point.laneX);
      if (hit.kind === "tick") {
        const ownerIds = hit.owners.map((track) => track.id);
        const policy = currentTimelinePolicy();
        const bounds = policy.retime
          ? keyframeRetimeBoundsFor({ entityId: slot.key, frame: hit.frame, trackletIds: ownerIds })
          : null;
        drag = {
          pointerId: event.pointerId,
          rowId: slot.key,
          ownerIds,
          state: pressKeyframe(point.laneX, hit.frame, bounds),
        };
        body?.setPointerCapture(event.pointerId);
        window.addEventListener("keydown", onDragKeydown, true);
        window.addEventListener("blur", cancelDrag);
        return;
      }
    }
    startScrub(event, point.laneX);
  }

  function flushMove() {
    moveRequest = 0;
    const move = pendingMove;
    pendingMove = null;
    if (!move) return;
    if (scrubPointerId !== null) {
      seekTimeline(xToFrame(geometry, move.laneX));
      return;
    }
    const slot = entitySlotAt(move.y);
    const model = slot ? models.get(slot.key) : undefined;
    const hit = slot && model ? hitTestLane(model.union, geometry, move.laneX) : null;
    hover = slot && hit?.kind === "tick" ? { slot, hit } : null;
    cursor = hover ? (currentTimelinePolicy().retime ? "grab" : "pointer") : "";
  }

  function onBodyPointerMove(event: PointerEvent) {
    if (drag && event.pointerId === drag.pointerId) {
      const point = bodyPoint(event);
      const { state, effect } = reduceKeyframeDrag(drag.state, {
        type: "move",
        x: point.laneX,
        pxPerFrame: geometry.pxPerFrame,
      });
      drag.state = state;
      if (effect.type === "preview" && state.phase === "dragging") {
        dragPreview = { rowId: drag.rowId, source: state.source, frame: effect.frame };
        cursor = "grabbing";
      }
      return;
    }
    if (scrubPointerId === null && (event.pointerType !== "mouse" || isOnHeader(event))) {
      hover = null;
      return;
    }
    pendingMove = bodyPoint(event);
    if (!moveRequest) moveRequest = requestAnimationFrame(flushMove);
  }

  function endDrag() {
    if (!drag) return;
    const pointerId = drag.pointerId;
    drag = null;
    dragPreview = null;
    cursor = "";
    window.removeEventListener("keydown", onDragKeydown, true);
    window.removeEventListener("blur", cancelDrag);
    if (body?.hasPointerCapture(pointerId)) body.releasePointerCapture(pointerId);
  }

  function cancelDrag() {
    if (!drag) return;
    reduceKeyframeDrag(drag.state, { type: "cancel" });
    endDrag();
  }

  // Esc during a drag only cancels it: it never reaches the canvas, the save form or the player.
  function onDragKeydown(event: KeyboardEvent) {
    if (event.key !== "Escape" || !drag) return;
    event.preventDefault();
    event.stopPropagation();
    cancelDrag();
  }

  function onBodyPointerUp(event: PointerEvent) {
    if (drag && event.pointerId === drag.pointerId) {
      const current = drag;
      const { effect } = reduceKeyframeDrag(current.state, { type: "up" });
      endDrag();
      const row = { rowId: current.rowId, topId: topIds.get(current.rowId) ?? current.rowId };
      if (effect.type === "click") {
        selectTimelineKeyframe(row, effect.frame);
      } else if (effect.type === "commit") {
        selectTimelineKeyframe(row, effect.from);
        retimeKeyframe({
          entityId: current.rowId,
          frame: effect.from,
          trackletIds: current.ownerIds,
          target: effect.to,
        });
      }
      return;
    }
    endScrub(event);
  }

  function endScrub(event: PointerEvent) {
    if (scrubPointerId !== event.pointerId) return;
    if (moveRequest) {
      cancelAnimationFrame(moveRequest);
      flushMove();
    }
    scrubPointerId = null;
    scrubbing = false;
    if (body?.hasPointerCapture(event.pointerId)) body.releasePointerCapture(event.pointerId);
  }

  function onBodyPointerCancel(event: PointerEvent) {
    if (drag && event.pointerId === drag.pointerId) cancelDrag();
    else endScrub(event);
  }

  // ─── Track menu ───────────────────────────────────────────────────────────

  let menuOpen = $state(false);
  let menuTarget = $state<TimelineMenuTarget | null>(null);
  let menuBlockedReason = $state<string | null>(null);

  function tracksOf(ids: readonly string[]): Tracklet[] {
    const wanted = new Set(ids);
    return tracks.value.filter((tracklet) => wanted.has(tracklet.id));
  }

  /** The tracks and frame a right-click points at: from the lane, or the current frame on a header. */
  function resolveMenuTarget(event: MouseEvent): TimelineMenuTarget | null {
    const onHeader = isOnHeader(event);
    const point = bodyPoint(event);
    let slot: Slot | null = null;
    if (onHeader && event.target instanceof Element) {
      const rowKey = event.target.closest("[data-timeline-row]")?.getAttribute("data-timeline-row");
      const index = rowKey ? layout.indexByKey.get(rowKey) : undefined;
      slot = index === undefined ? null : layout.slots[index];
    } else if (!onHeader) {
      slot = entitySlotAt(point.y);
    }
    if (!slot || slot.kind !== "entity") return null;
    const model = models.get(slot.key);
    const entity = entitiesById.get(slot.key);
    if (!model || !entity) return null;
    let frame: number;
    let ids: string[];
    if (onHeader) {
      frame = currentFrameIndex.value;
      ids = tracksCoveringFrame(model.union, frame).map((track) => track.id);
    } else {
      const hit = hitTestLane(model.union, geometry, point.laneX);
      if (hit.kind === "gap") return null;
      frame = hit.frame;
      ids = (hit.kind === "tick" ? hit.owners : hit.tracks).map((track) => track.id);
    }
    if (ids.length === 0) return null;
    return { entity, topId: topIds.get(entity.id) ?? entity.id, frame, tracks: tracksOf(ids) };
  }

  function onBodyContextMenu(event: MouseEvent) {
    if (drag) {
      event.preventDefault();
      cancelDrag();
      return;
    }
    const target = resolveMenuTarget(event);
    if (!target) {
      // An empty spot only leaves the drawing tool, as before; no menu opens.
      event.preventDefault();
      menuTarget = null;
      leaveDrawingTool();
      return;
    }
    const policy = currentTimelinePolicy();
    menuBlockedReason = policy.menu === "notice" ? policy.reason : null;
    menuTarget = target;
  }

  // ─── Overlays ─────────────────────────────────────────────────────────────

  const playheadX = $derived(frameToX(geometry, currentFrameIndex.value));

  // The keyframe under the playhead on the selected row, or the one being dragged.
  const selectedMark = $derived.by<OverlayMark | null>(() => {
    if (dragPreview) {
      const index = layout.indexByKey.get(dragPreview.rowId);
      const lane = models.get(dragPreview.rowId)?.union;
      if (index === undefined || !lane) return null;
      return {
        x: frameToX(geometry, dragPreview.frame),
        laneTop: layout.slots[index].contentTop,
        box: MARKS_ENTITY.selected,
        color: keyframeColorAt(lane, dragPreview.source),
      };
    }
    const lane = timelineNavLane.value;
    const index = selectedRowId ? layout.indexByKey.get(selectedRowId) : undefined;
    const frame = currentFrameIndex.value;
    if (!lane || index === undefined || keyframeIndexAt(lane.frames, frame) < 0) return null;
    return {
      x: frameToX(geometry, frame),
      laneTop: layout.slots[index].contentTop,
      box: MARKS_ENTITY.selected,
      color: keyframeColorAt(lane, frame),
    };
  });

  const hoverMark = $derived.by<OverlayMark | null>(() => {
    if (!hover || dragPreview) return null;
    const lane = models.get(hover.slot.key)?.union;
    if (!lane) return null;
    return {
      x: frameToX(geometry, hover.hit.frame),
      laneTop: hover.slot.contentTop,
      box: hover.hit.isCap ? MARKS_ENTITY.hoverCap : MARKS_ENTITY.hoverTick,
      color: keyframeColorAt(lane, hover.hit.frame),
    };
  });

  const tooltip = $derived.by<OverlayTooltip | null>(() => {
    const preview = dragPreview;
    if (preview) {
      const index = layout.indexByKey.get(preview.rowId);
      if (index === undefined) return null;
      const slot = layout.slots[index];
      return {
        text: formatTickTooltip(preview.frame, formatTimecode(frameTime(preview.frame, fps))),
        x: frameToX(geometry, preview.frame),
        rowTop: slot.contentTop,
        rowHeight: slot.height - (slot.contentTop - slot.top),
      };
    }
    if (!hover) return null;
    const views = [...new Set(hover.hit.owners.map((track) => track.view))];
    return {
      text: formatTickTooltip(
        hover.hit.frame,
        formatTimecode(frameTime(hover.hit.frame, fps)),
        views,
      ),
      x: frameToX(geometry, hover.hit.frame),
      rowTop: hover.slot.contentTop,
      rowHeight: hover.slot.height - (hover.slot.contentTop - hover.slot.top),
    };
  });

  // ─── Scrolling, zoom and reveal ───────────────────────────────────────────

  function onScroll() {
    if (scrollRequest) return;
    scrollRequest = requestAnimationFrame(() => {
      scrollRequest = 0;
      if (!scroller) return;
      scrollLeft = scroller.scrollLeft;
      scrollTop = scroller.scrollTop;
      if (scrubPointerId === null && !drag) hover = null;
    });
  }

  /** Zoom while keeping the playhead (or the middle of the view) where it is on screen. */
  async function applyZoom(next: number) {
    const clamped = Math.round(Math.min(zoomMax, Math.max(TIMELINE_ZOOM_MIN, next)));
    if (clamped === zoom) return;
    if (!scroller) {
      timelineZoom.value = [clamped];
      return;
    }
    const previous = geometry;
    const anchor = zoomAnchorFrame(
      previous,
      scroller.scrollLeft,
      viewportWidth,
      currentFrameIndex.value,
    );
    const nextGeometry = createTimelineGeometry(
      lastFrameIndex.value,
      laneWidthForZoom(viewportWidth, clamped),
    );
    const left = anchoredScrollLeft(
      previous,
      nextGeometry,
      scroller.scrollLeft,
      anchor,
      viewportWidth,
    );
    scrollLeft = left;
    timelineZoom.value = [clamped];
    await tick();
    if (scroller) scroller.scrollLeft = left;
  }

  // The device pixel ratio changes with the screen or the browser zoom; resizes follow it.
  $effect(() => {
    void clientWidth;
    dpr = window.devicePixelRatio || 1;
  });

  // Another record: start from the beginning of the timeline.
  $effect(() => {
    void currentItemId.value;
    untrack(() => {
      cancelDrag();
      hover = null;
      scrollLeft = 0;
      scrollTop = 0;
      scroller?.scrollTo({ left: 0, top: 0 });
    });
  });

  // A tracking session's row is the first one: show it when the session starts.
  let hadSession = false;
  $effect(() => {
    const active = sessionState !== null;
    if (active && !hadSession) untrack(() => scroller?.scrollTo({ top: 0 }));
    hadSession = active;
  });

  // The selected row comes into view, whichever way it was selected (inspector, canvas, E).
  $effect(() => {
    const rowId = timelineSelectedRowId.value;
    if (!rowId) return;
    void tick().then(() => {
      untrack(() => {
        const index = layout.indexByKey.get(rowId);
        // Before the scroller is measured, every row would look out of view.
        if (index === undefined || !scroller || bodyViewportHeight <= 0) return;
        const top = revealScrollTop(layout.slots[index], scroller.scrollTop, bodyViewportHeight);
        if (top !== null) scroller.scrollTo({ top });
      });
    });
  });

  // The playhead stays in view when the frame changes from elsewhere (keys, playback, canvas).
  $effect(() => {
    const frame = currentFrameIndex.value;
    untrack(() => {
      if (!scroller || scrubbing || drag) return;
      const left = revealScrollLeft(geometry, scroller.scrollLeft, viewportWidth, frame);
      if (left === null) return;
      scrollLeft = left;
      scroller.scrollLeft = left;
    });
  });

  onDestroy(() => {
    cancelAnimationFrame(moveRequest);
    cancelAnimationFrame(scrollRequest);
    cancelDrag();
  });
</script>

{#if playbackState.value.isLoaded}
  <div data-timeline-root class="flex h-full flex-col overflow-hidden bg-card">
    <TimelineCommandBar
      time={formatTimecode(frameTime(currentFrameIndex.value, fps))}
      buffering={playbackState.value.isBuffering}
      pinnedCount={rowList.pinnedCount}
      pinnedOnly={rowList.pinnedOnly}
      {zoom}
      {zoomMax}
      {resetHighlight}
      onTogglePinnedOnly={toggleTimelinePinnedOnly}
      onZoom={(next) => void applyZoom(next)}
    />

    <div
      bind:this={scroller}
      bind:clientWidth
      bind:clientHeight
      onscroll={onScroll}
      class="relative min-h-0 flex-1 select-none overflow-auto overscroll-contain"
      data-timeline-scroller
    >
      <div class="relative isolate" style:width="{TIMELINE_HEADER_WIDTH + laneWidth}px">
        <div class="sticky top-0 z-30 flex" style:height="{RULER_BAND_HEIGHT}px">
          <div class="sticky left-0 z-40 shrink-0 bg-card" style:width="{TIMELINE_HEADER_WIDTH}px">
            <div
              class="flex h-11 items-center gap-1.5 border-b border-border bg-timeline-ruler px-3 font-mono text-[11px]"
            >
              {#if corner.fps}
                <span class="text-foreground">{corner.fps}</span>
                <span class="text-foreground/65" aria-hidden="true">·</span>
              {/if}
              <span class="text-foreground/65">{corner.frames}</span>
            </div>
          </div>
          <div class="relative shrink-0" style:width="{laneWidth}px">
            <TimelineRuler
              {laneWidth}
              currentFrame={currentFrameIndex.value}
              onSeek={(frame) => seekTimeline(frame)}
              onScrubChange={(active: boolean) => {
                scrubbing = active;
              }}
            />
            <TimelineDensityStrip {laneWidth} spans={densitySpans} />
          </div>
        </div>

        <ContextMenu.Root bind:open={menuOpen}>
          <ContextMenu.Trigger class="block">
            <div
              bind:this={body}
              data-timeline-body
              class="relative"
              style:height="{bodyHeight}px"
              style:cursor={cursor || undefined}
              role="list"
              aria-label="Tracked objects"
              onpointerdown={onBodyPointerDown}
              onpointermove={onBodyPointerMove}
              onpointerup={onBodyPointerUp}
              onpointercancel={onBodyPointerCancel}
              onlostpointercapture={onBodyPointerCancel}
              onpointerleave={() => {
                if (scrubPointerId === null && !drag) {
                  hover = null;
                  cursor = "";
                }
              }}
              oncontextmenu={onBodyContextMenu}
            >
              {#if sessionState}
                <TrackingTimelineRow state={sessionState} height={sessionHeight} {laneWidth} />
              {/if}
              {#if detectionLanes.length > 0}
                <DetectionTracksTimelineRows
                  lanes={detectionLanes}
                  height={detectionHeight}
                  {laneWidth}
                  onSelect={(trackId, startFrame) => {
                    selectDetectionTrack(trackId);
                    seekTimeline(startFrame);
                  }}
                />
              {/if}
              {#each rowList.ids as rowId (rowId)}
                {@const entity = entitiesById.get(rowId)}
                {@const model = models.get(rowId)}
                {@const slot = layout.slots[layout.indexByKey.get(rowId) ?? -1]}
                {#if entity && model && slot}
                  <div role="listitem">
                    <EntityTimelineRow
                      {entity}
                      {model}
                      height={slot.height}
                      {laneWidth}
                      dotColor={annotationColors.value.colorOfEntity(rowId)}
                      selected={selectedRowId === rowId}
                      pinned={rowList.pinnedIds.has(rowId)}
                      graphicsOpacity={rowGraphics.get(rowId) ?? 1}
                      marksVisible={slotInRange(slot, yRange)}
                      editing={editingRowId === rowId}
                      editUnavailableReason={editUnavailableReason(model)}
                      onSelect={() => onSelectRow(rowId, model)}
                      onTogglePin={() => togglePinnedTimelineEntity(rowId)}
                      onTogglePencil={() => onTogglePencil(rowId, model)}
                    />
                  </div>
                {/if}
              {/each}
              {#if emptyState}
                <p
                  class="sticky left-0 px-3 py-2 text-xs text-foreground/65"
                  style:width="{TIMELINE_HEADER_WIDTH + viewportWidth}px"
                >
                  {TIMELINE_EMPTY_TEXT[emptyState]}
                </p>
              {/if}
              <TimelineOverlays
                {playheadX}
                {bodyHeight}
                selected={selectedMark}
                hover={hoverMark}
                {tooltip}
                {scrollLeft}
                {scrollTop}
                {viewportWidth}
              />
            </div>
          </ContextMenu.Trigger>
          <ContextMenu.Portal>
            <ContextMenu.Content
              class="z-[130] min-w-52 max-w-80 rounded-xl border border-border/50 bg-popover/95 p-1 text-popover-foreground shadow-elevation-2 backdrop-blur-md"
              onkeydown={(event) => handleMenuKeydown(event, true, () => (menuOpen = false))}
              onCloseAutoFocus={(event) => event.preventDefault()}
            >
              {#if menuTarget}
                <TimelineTrackMenu
                  target={menuTarget}
                  blockedReason={menuBlockedReason}
                  onClose={() => (menuOpen = false)}
                />
              {/if}
            </ContextMenu.Content>
          </ContextMenu.Portal>
        </ContextMenu.Root>
      </div>
    </div>
  </div>
{/if}
