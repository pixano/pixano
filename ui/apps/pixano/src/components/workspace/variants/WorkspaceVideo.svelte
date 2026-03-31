<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Canvas2D } from "$components/workspace/canvas2d";
  import { untrack } from "svelte";

  import TimelinePanel from "../VideoPlayer/TimelinePanel.svelte";
  import {
    resolveVideoMaskResetAction,
    shouldClearVideoMaskSessionOnToolSwitch,
    shouldHydrateVideoPreview,
  } from "./videoMaskSessionLifecycle";
  import { buildCurrentSequenceFrameLocatorsByView } from "./videoSequenceFrameRefs";
  import { navigating } from "$app/state";
  import { saveMaskShapeToTrackingOutput } from "$lib/segmentation/maskNormalization";
  import {
    createErrorSmartSegmentationUiState,
    createIdleSmartSegmentationUiState,
    createPendingSmartSegmentationUiState,
  } from "$lib/segmentation/smartInferenceStatus";
  import {
    pixanoInferenceToValidateTrackingMasks,
    selectedVideoSegmentationModel,
  } from "$lib/stores/inferenceStores.svelte";
  import {
    addTrackingKeyframe,
    beginVosPendingInterval,
    cancelTrackingSession,
    commitVosInterval,
    confirmPendingKeyframe,
    discardPendingKeyframe,
    failVosPendingInterval,
    finalizeTrackingSession,
    hasPendingKeyframe,
    isAwaitingNewSegmentKeyframe,
    isTracking,
    isVosSessionActive,
    pendingKeyframeIndex,
    resetVosSession,
    setPendingKeyframe,
    setVosAnchor,
    startNewTrackingSegment,
    startNewVosSegment,
    startTrackingSession,
    trackingPreviewBBoxes,
    vosAnchorFrameIndex,
    vosSession,
    vosTrackedMasks,
  } from "$lib/stores/trackingStore.svelte";
  import {
    currentFrameIndex,
    currentItemId,
    imagesPerView,
    lastFrameIndex,
    playbackState,
    resetVideoStores,
    videoViewNames,
  } from "$lib/stores/videoStores.svelte";
  import {
    annotations,
    brushSettings,
    colorScale,
    current_itemBBoxes,
    current_itemKeypoints,
    current_itemMasks,
    current_itemMultiPaths,
    entities,
    imageSmoothing,
    newShape,
    selectedTool,
    smartSegmentationUiState,
  } from "$lib/stores/workspaceStores.svelte";
  import {
    ToolType,
    vosTool,
    type InteractiveSegmenterAIInput,
    type SelectionTool,
  } from "$lib/tools";
  import { Sam2VideoTracker } from "$lib/trackers";
  import type { VideoTrackingJobStatus } from "$lib/types/inference";
  import { toLegacyReference } from "$lib/types/workspaceLocators";
  import type { WorkspaceViewerItem } from "$lib/types/workspace";
  import {
    AiProcessingBadge,
    SequenceFrame,
    ShapeType,
    type EditShape,
    type SaveMaskShape,
  } from "$lib/ui";
  import {
    tryHighlightSelectionShape,
    updateExistingAnnotation,
  } from "$lib/utils/entityAnnotationEditing";
  import { scrollIntoView } from "$lib/utils/highlightOperations";
  import { saveTo } from "$lib/utils/saveItemUtils";
  import { toggleFusionEntity } from "$lib/utils/videoFusion";
  import { loadInitialFrames, setBufferSpecs } from "$lib/utils/videoOperations";
  import { editKeyItemInTracklet } from "$lib/utils/videoShapeEditing";
  import { commitNormalizedWorkspaceRuntime } from "$lib/utils/workspaceRuntimeMutations";

  interface Props {
    selectedItem: WorkspaceViewerItem;
    resize: number;
  }

  interface BrushSettings {
    brushRadius: number;
    lazyRadius: number;
    friction: number;
  }

  let { selectedItem, resize }: Props = $props();

  $effect(() => {
    if (selectedItem) {
      currentFrameIndex.value = 0;
    }
  });

  let inspectorMaxHeight = $state(250);
  let expanding = $state(false);
  let isLoaded = $state(false);
  let loadingCycle = 0;
  let lastLoadedVideoKey = "";
  let sam2Tracker = $state<Sam2VideoTracker | null>(null);
  let smartPreviewMasks = $state<Record<string, SaveMaskShape | null>>({});
  let activeVosJob = $state<{
    requestId: string;
    jobId: string | null;
    kind: "preview" | "interval";
    viewName: string;
    tracker: Sam2VideoTracker;
  } | null>(null);
  const isRouteLoading = $derived(navigating.from !== null);
  const TRACKING_JOB_POLL_MS = 500;

  function getSequenceFrameViews(item: WorkspaceViewerItem): Record<string, SequenceFrame[]> {
    const entries = Object.entries(item.views).flatMap(([viewName, view]) => {
      if (!Array.isArray(view) || view.length === 0) {
        return [];
      }
      return [[viewName, view as SequenceFrame[]] as const];
    });
    return Object.fromEntries(entries);
  }

  function clearSmartPreview(viewName?: string): void {
    untrack(() => {
      if (viewName) {
        if (!(viewName in smartPreviewMasks)) return;
        const next = { ...smartPreviewMasks };
        delete next[viewName];
        smartPreviewMasks = next;
        return;
      }

      if (Object.keys(smartPreviewMasks).length === 0) return;
      smartPreviewMasks = {};
    });
  }

  function setSmartPreview(viewName: string, mask: SaveMaskShape): void {
    untrack(() => {
      if (smartPreviewMasks[viewName] === mask) return;
      smartPreviewMasks = {
        ...smartPreviewMasks,
        [viewName]: mask,
      };
    });
  }

  function resetSmartTracking(): void {
    void cancelActiveVosJob();
    clearSmartPreview();
    sam2Tracker?.clear();
    sam2Tracker = null;
    resetVosSession();
    smartSegmentationUiState.value = createIdleSmartSegmentationUiState();
    pixanoInferenceToValidateTrackingMasks.value = [];
  }

  function resetSmartSegmentationFeedback(): void {
    smartSegmentationUiState.value = createIdleSmartSegmentationUiState();
  }

  function consumeResetStateOnNextMicrotask(shape: typeof newShape.value): void {
    queueMicrotask(() => {
      if (newShape.value === shape) {
        newShape.value = { status: "none" };
      }
    });
  }

  function resolveFrameSources(viewName: string) {
    const frames = selectedItem.views?.[viewName] as SequenceFrame[] | undefined;
    if (!Array.isArray(frames)) return [];
    return frames.map((frame) => ({
      frameIndex: Number(frame.data.frame_index),
      viewRef: { id: frame.id, name: viewName },
      width: Number(frame.data.width),
      height: Number(frame.data.height),
    }));
  }

  function resolveFrameIndex(viewRef: { id: string; name: string }): number | null {
    const frames = selectedItem.views?.[viewRef.name] as SequenceFrame[] | undefined;
    if (!Array.isArray(frames)) return null;
    const frame = frames.find((candidate) => candidate.id === viewRef.id);
    return frame ? Number(frame.data.frame_index) : null;
  }

  function resolveViewRefByFrameIndex(
    viewName: string,
    frameIndex: number,
  ): { id: string; name: string } | null {
    const frames = selectedItem.views?.[viewName] as SequenceFrame[] | undefined;
    if (!Array.isArray(frames)) return null;
    const frame = frames.find((candidate) => Number(candidate.data.frame_index) === frameIndex);
    return frame ? { id: frame.id, name: viewName } : null;
  }

  const currentSequenceFrameLocatorsByView = $derived.by(() => {
    const frameIndex = currentFrameIndex.value;
    return buildCurrentSequenceFrameLocatorsByView(getSequenceFrameViews(selectedItem), frameIndex);
  });

  const currentSequenceFrameRefsByView = $derived.by(() => {
    return Object.fromEntries(
      Object.entries(currentSequenceFrameLocatorsByView).map(([logicalName, locator]) => [
        logicalName,
        toLegacyReference(locator),
      ]),
    );
  });

  function sleep(ms: number): Promise<void> {
    return new Promise((resolve) => {
      setTimeout(resolve, ms);
    });
  }

  async function cancelActiveVosJob(): Promise<void> {
    const job = activeVosJob;
    if (!job) {
      return;
    }

    activeVosJob = null;
    if (!job.jobId) {
      return;
    }

    try {
      await job.tracker.cancelTrackingJob(job.jobId);
    } catch (error) {
      console.warn("Failed to cancel tracking job", error);
    }
  }

  async function runVosTrackingJob({
    requestId,
    viewName,
    tracker,
    kind,
    submit,
  }: {
    requestId: string;
    viewName: string;
    tracker: Sam2VideoTracker;
    kind: "preview" | "interval";
    submit: () => Promise<VideoTrackingJobStatus | null>;
  }): Promise<VideoTrackingJobStatus | null> {
    await cancelActiveVosJob();
    activeVosJob = {
      requestId,
      jobId: null,
      kind,
      viewName,
      tracker,
    };

    try {
      const submittedJob = await submit();
      if (!submittedJob) {
        if (activeVosJob?.requestId === requestId) {
          activeVosJob = null;
        }
        return null;
      }

      if (activeVosJob?.requestId !== requestId) {
        try {
          await tracker.cancelTrackingJob(submittedJob.job_id);
        } catch (error) {
          console.warn("Failed to cancel stale tracking job", error);
        }
        return null;
      }

      activeVosJob = {
        requestId,
        jobId: submittedJob.job_id,
        kind,
        viewName,
        tracker,
      };

      if (
        submittedJob.status === "completed" ||
        submittedJob.status === "failed" ||
        submittedJob.status === "canceled"
      ) {
        if (activeVosJob?.requestId === requestId) {
          activeVosJob = null;
        }
        return submittedJob;
      }

      while (activeVosJob?.requestId === requestId && activeVosJob?.jobId === submittedJob.job_id) {
        await sleep(TRACKING_JOB_POLL_MS);
        if (activeVosJob?.requestId !== requestId || activeVosJob?.jobId !== submittedJob.job_id) {
          return null;
        }

        const polledJob = await tracker.getTrackingJobStatus(submittedJob.job_id);
        if (activeVosJob?.requestId !== requestId || activeVosJob?.jobId !== submittedJob.job_id) {
          return null;
        }

        if (polledJob.status === "queued" || polledJob.status === "running") {
          continue;
        }

        activeVosJob = null;
        return polledJob;
      }

      return null;
    } catch (error) {
      if (activeVosJob?.requestId === requestId) {
        activeVosJob = null;
      }
      throw error;
    }
  }

  function getOrCreateTracker(viewName: string): Sam2VideoTracker | null {
    const frameSources = resolveFrameSources(viewName);
    if (frameSources.length === 0) {
      return null;
    }

    const tracker =
      sam2Tracker && sam2Tracker.viewName === viewName
        ? sam2Tracker
        : new Sam2VideoTracker(selectedItem.ui.datasetId, selectedItem.item.id, viewName);
    tracker.setFrameSources(frameSources);
    sam2Tracker = tracker;
    return tracker;
  }

  function buildTrackerPrompt(
    prompt: InteractiveSegmenterAIInput["prompt"] | null,
    mask: SaveMaskShape | null,
  ) {
    return {
      points:
        prompt?.points.map((point) => ({
          x: point.x,
          y: point.y,
          label: point.label as 0 | 1,
        })) ?? [],
      box: prompt?.box
        ? {
            x: prompt.box.x,
            y: prompt.box.y,
            width: prompt.box.width,
            height: prompt.box.height,
          }
        : null,
      mask,
    };
  }

  function syncVosTrackingOutputs(): void {
    pixanoInferenceToValidateTrackingMasks.value = vosTrackedMasks.value;
  }

  function getCurrentVosSaveMask(): SaveMaskShape | null {
    const tracker = sam2Tracker;
    const currentMask = tracker?.interpolateAt(currentFrameIndex.value)?.data.mask ?? null;
    if (currentMask) {
      return currentMask;
    }
    return vosSession.value.anchor?.mask ?? null;
  }

  async function handleVosTrack(): Promise<void> {
    const modelSelection = selectedVideoSegmentationModel.value;
    const anchor = vosSession.value.anchor;
    if (!modelSelection || !anchor) return;

    const targetFrame = currentFrameIndex.value;
    if (targetFrame <= anchor.frameIndex) {
      smartSegmentationUiState.value = createErrorSmartSegmentationUiState(
        `vos-track-${Date.now()}`,
        anchor.viewRef.name,
        new Error("Tracking currently supports only later end frames."),
      );
      return;
    }

    const requestId = `vos-track-${Date.now()}`;
    beginVosPendingInterval({
      requestId,
      startFrame: anchor.frameIndex,
      endFrame: targetFrame,
      direction: "forward",
    });
    smartSegmentationUiState.value = createPendingSmartSegmentationUiState(
      requestId,
      anchor.viewRef.name,
      "Tracking in progress...",
    );

    const tracker = getOrCreateTracker(anchor.viewRef.name);
    if (!tracker) {
      failVosPendingInterval(requestId);
      smartSegmentationUiState.value = createErrorSmartSegmentationUiState(
        requestId,
        anchor.viewRef.name,
        new Error(`Could not resolve the current SequenceFrame for view '${anchor.viewRef.name}'.`),
      );
      return;
    }

    const keyframe = {
      frameIndex: anchor.frameIndex,
      viewRef: anchor.viewRef,
      objectId: 1,
      model: modelSelection.name,
      providerName: modelSelection.provider_name,
      itemId: selectedItem.item.id,
      prompt: buildTrackerPrompt(anchor.prompt, anchor.sourceKind === "mask" ? anchor.mask : null),
      mask: anchor.mask,
    };

    tracker.addKeyframe(keyframe);

    try {
      const jobStatus = await runVosTrackingJob({
        requestId,
        viewName: anchor.viewRef.name,
        tracker,
        kind: "interval",
        submit: () => tracker.submitPropagateIntervalJob(anchor.frameIndex, targetFrame, keyframe),
      });

      if (smartSegmentationUiState.value.requestId !== requestId) {
        return;
      }

      if (!jobStatus || jobStatus.status === "canceled") {
        return;
      }

      if (jobStatus.status !== "completed") {
        throw new Error(jobStatus.detail ?? "Tracking job failed.");
      }

      tracker.applyTrackingResult(jobStatus.data, keyframe);
      const targetMask = tracker.interpolateAt(targetFrame)?.data.mask ?? null;
      const targetViewRef = resolveViewRefByFrameIndex(anchor.viewRef.name, targetFrame);
      const intervalOutputs = tracker.getTrackingOutputsInRange(anchor.frameIndex, targetFrame);
      if (!targetMask || !targetViewRef || intervalOutputs.length === 0) {
        failVosPendingInterval(requestId);
        smartSegmentationUiState.value = createErrorSmartSegmentationUiState(
          requestId,
          anchor.viewRef.name,
          new Error("Tracking did not return any masks for the requested interval."),
        );
        return;
      }

      commitVosInterval({
        requestId,
        outputs: intervalOutputs,
        nextAnchor: {
          frameIndex: targetFrame,
          viewRef: targetViewRef,
          sourceKind: "mask",
          prompt: null,
          mask: targetMask,
        },
      });
      syncVosTrackingOutputs();
      resetSmartSegmentationFeedback();

      const currentMask = tracker.interpolateAt(currentFrameIndex.value)?.data.mask ?? targetMask;
      setSmartPreview(anchor.viewRef.name, currentMask);
    } catch (error) {
      if (smartSegmentationUiState.value.requestId !== requestId) {
        return;
      }

      failVosPendingInterval(requestId);
      smartSegmentationUiState.value = createErrorSmartSegmentationUiState(
        requestId,
        anchor.viewRef.name,
        error,
      );
    }
  }

  async function handleSmartSegmentationRequest(
    requestId: string,
    request: InteractiveSegmenterAIInput,
  ): Promise<void> {
    if (request.action === "clear") {
      resetSmartTracking();
      return;
    }

    const isVos = selectedTool.value?.type === ToolType.VOS;
    if (isVos && !isVosSessionActive.value && isTracking.value) {
      cancelTrackingSession();
    }
    const modelSelection = selectedVideoSegmentationModel.value;
    if (!modelSelection) return;

    if (request.action === "confirm") {
      if (isVos) {
        return;
      }

      const previewMask = smartPreviewMasks[request.viewRef.name];
      if (!previewMask) return;
      newShape.value = previewMask;
      return;
    }

    const frameIndex = resolveFrameIndex(request.viewRef);
    const tracker = getOrCreateTracker(request.viewRef.name);
    if (!tracker || frameIndex === null) {
      smartSegmentationUiState.value = createErrorSmartSegmentationUiState(
        requestId,
        request.viewRef.name,
        new Error(
          `Could not resolve the current SequenceFrame for view '${request.viewRef.name}'.`,
        ),
      );
      return;
    }

    smartSegmentationUiState.value = createPendingSmartSegmentationUiState(
      requestId,
      request.viewRef.name,
      "Tracking in progress...",
    );

    try {
      const keyframe = {
        frameIndex,
        viewRef: request.viewRef,
        objectId: 1,
        model: modelSelection.name,
        providerName: modelSelection.provider_name,
        itemId: selectedItem.item.id,
        prompt: {
          points: request.prompt.points.map((point) => ({
            x: point.x,
            y: point.y,
            label: point.label as 0 | 1,
          })),
          box: request.prompt.box
            ? {
                x: request.prompt.box.x,
                y: request.prompt.box.y,
                width: request.prompt.box.width,
                height: request.prompt.box.height,
              }
            : null,
        },
      };

      const jobStatus = await runVosTrackingJob({
        requestId,
        viewName: request.viewRef.name,
        tracker,
        kind: "preview",
        submit: () => tracker.submitPredictKeyframeJob(keyframe),
      });

      if (smartSegmentationUiState.value.requestId !== requestId) {
        return;
      }

      if (!jobStatus || jobStatus.status === "canceled") {
        return;
      }

      if (jobStatus.status !== "completed") {
        throw new Error(jobStatus.detail ?? "Tracking job failed.");
      }

      const previewMask = tracker.applyTrackingResult(jobStatus.data, keyframe)[0] ?? null;
      if (!previewMask) {
        throw new Error("Tracking did not return a mask for the prompted frame.");
      }
      const previewOutput =
        tracker.getTrackingOutputsInRange(frameIndex, frameIndex)[0] ??
        saveMaskShapeToTrackingOutput(previewMask, frameIndex, {
          modelName: modelSelection.name,
          providerName: modelSelection.provider_name,
        });

      resetSmartSegmentationFeedback();
      setSmartPreview(request.viewRef.name, previewMask);

      if (isVos) {
        setVosAnchor({
          frameIndex,
          viewRef: request.viewRef,
          sourceKind: "prompt",
          prompt: request.prompt,
          mask: previewMask,
          output: previewOutput,
        });
        syncVosTrackingOutputs();
      }
    } catch (error) {
      if (smartSegmentationUiState.value.requestId !== requestId) {
        return;
      }

      smartSegmentationUiState.value = createErrorSmartSegmentationUiState(
        requestId,
        request.viewRef.name,
        error,
      );
    }
  }

  const handleCanvasShapeChange = (shape: import("$lib/ui").Shape) => {
    // Draft creation now stays local in Canvas2D and should not trigger store churn.
    if (shape.status === "creating") return;

    // Intercept bbox saves to start/extend a tracking session
    if (shape.status === "saving" && shape.type === ShapeType.bbox) {
      if (!isTracking.value && isVosSessionActive.value) {
        resetSmartTracking();
      }

      const saveShape = shape;
      const { viewRef, itemId, imageWidth, imageHeight, attrs } = saveShape;

      if (!isTracking.value) {
        startTrackingSession(viewRef.name, viewRef, itemId, imageWidth, imageHeight);
      }

      if (hasPendingKeyframe.value) discardPendingKeyframe();

      const normalizedCoords: [number, number, number, number] = [
        attrs.x / imageWidth,
        attrs.y / imageHeight,
        attrs.width / imageWidth,
        attrs.height / imageHeight,
      ];
      addTrackingKeyframe(currentFrameIndex.value, normalizedCoords);

      // Prevent SaveShapeForm from appearing
      newShape.value = { status: "none", shouldReset: true };
      return;
    }

    newShape.value = shape;
  };

  // ─── Video loading ──────────────────────────────────────────────────────────

  $effect(() => {
    const nextItemId = selectedItem?.item?.id;
    if (!nextItemId) return;

    const datasetId = selectedItem.ui.datasetId;
    const nextViews = getSequenceFrameViews(selectedItem);
    const viewNames = Object.keys(nextViews);
    const longestView = viewNames.length
      ? Math.max(...Object.values(nextViews).map((view) => view.length))
      : 0;
    const nextLoadKey = `${nextItemId}:${viewNames.map((viewName) => `${viewName}:${nextViews[viewName].length}`).join("|")}`;
    if (!viewNames.length || longestView <= 0) {
      lastLoadedVideoKey = "";
      isLoaded = false;
      resetSmartTracking();
      resetVideoStores();
      return;
    }
    if (nextLoadKey === lastLoadedVideoKey) return;
    lastLoadedVideoKey = nextLoadKey;

    untrack(() => {
      const cycle = ++loadingCycle;

      clearInterval(playbackState.value.intervalId);
      playbackState.update((old) => ({
        ...old,
        intervalId: 0,
        isLoaded: false,
        isBuffering: false,
      }));
      isLoaded = false;
      resetSmartTracking();

      currentItemId.value = nextItemId;
      videoViewNames.value = viewNames;

      lastFrameIndex.value = longestView - 1;
      setBufferSpecs();

      void loadInitialFrames(datasetId)
        .then(() => {
          if (cycle !== loadingCycle) return;
          isLoaded = true;
          playbackState.update((old) => ({ ...old, isLoaded: true, isBuffering: false }));
        })
        .catch((error) => {
          if (cycle !== loadingCycle) return;
          console.error("Failed to load initial video frames", error);
          isLoaded = false;
          playbackState.update((old) => ({ ...old, isLoaded: false, isBuffering: false }));
        });
    });
  });

  // ─── Shape editing ──────────────────────────────────────────────────────────

  const updateOrCreateShape = (shape: EditShape) => {
    if (tryHighlightSelectionShape(shape, annotations.value)) {
      newShape.value = { status: "none" };
      return;
    }

    if (shape.type === ShapeType.bbox || shape.type === ShapeType.keypoints) {
      const { objects, save_data } = editKeyItemInTracklet(
        annotations.value,
        shape,
        currentFrameIndex.value,
        current_itemBBoxes.value,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        current_itemKeypoints.value as any,
      );
      commitNormalizedWorkspaceRuntime(objects, entities.value);
      if (save_data) saveTo(save_data.change_type, save_data.data);
    } else {
      annotations.update((objects) => updateExistingAnnotation(objects, shape));
    }
    newShape.value = { status: "none" };
  };

  $effect(() => {
    const shape = newShape.value;
    if (!shape || shape.status !== "editing") return;

    const toolType = selectedTool.value?.type ?? ToolType.Pan;
    untrack(() => {
      // Edit-during-tracking: stage as pending keyframe (user confirms with T)
      // editCoords from BBox2D are already normalized [0,1]
      if (isTracking.value && shape.type === ShapeType.bbox) {
        const editCoords = (shape as EditShape & { coords: number[] }).coords;
        setPendingKeyframe(currentFrameIndex.value, [
          editCoords[0],
          editCoords[1],
          editCoords[2],
          editCoords[3],
        ]);
        newShape.value = { status: "none" };
        return;
      }

      if (toolType !== ToolType.Fusion) {
        updateOrCreateShape(shape);
      } else {
        if (shape.top_entity_id) {
          scrollIntoView(shape.top_entity_id);
        }
      }
    });
  });

  // ─── Inspector resize ───────────────────────────────────────────────────────

  const expand = (e: MouseEvent) => {
    if (expanding) {
      inspectorMaxHeight = document.body.scrollHeight - e.pageY;
    }
  };

  // ─── Fusion merge (passed to Canvas2D) ──────────────────────────────────────

  const merge = (clickedAnn: import("$lib/ui").Annotation) => {
    if (selectedTool.value?.type === ToolType.Fusion) {
      toggleFusionEntity(clickedAnn);
    }
  };

  // ─── Tracking: merged bboxes (existing + preview) ─────────────────────────

  const mergedBBoxes = $derived([
    ...(current_itemBBoxes.value ?? []),
    ...(newShape.value?.status === "saving" ? [] : trackingPreviewBBoxes.value),
  ]);

  // ─── Tracking: keyboard handler ───────────────────────────────────────────

  const handleTrackingKeydown = (event: KeyboardEvent) => {
    const isVos = selectedTool.value?.type === ToolType.VOS;
    if (!isTracking.value && !isVos) return;
    const tag = (event.target as HTMLElement)?.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

    if (event.key === "n" || event.key === "N") {
      event.preventDefault();
      event.stopImmediatePropagation();
      if (isVos) {
        if (smartSegmentationUiState.value.phase === "pending") return;
        startNewVosSegment();
        return;
      }
      if (hasPendingKeyframe.value) confirmPendingKeyframe();
      startNewTrackingSegment();
      return;
    }
    if (event.key === "t" || event.key === "T") {
      if (isVos) {
        event.preventDefault();
        event.stopImmediatePropagation();
        void handleVosTrack();
        return;
      }

      if (hasPendingKeyframe.value) {
        event.preventDefault();
        event.stopImmediatePropagation();
        confirmPendingKeyframe();
        return;
      }
      return; // no pending → let Canvas2D handle T for rectangle draft
    }
    if (event.key === "Enter") {
      if (isVos) {
        event.preventDefault();
        event.stopImmediatePropagation();
        if (smartSegmentationUiState.value.phase === "pending") return;
        const saveMask = getCurrentVosSaveMask();
        if (!saveMask || vosTrackedMasks.value.length === 0) return;
        syncVosTrackingOutputs();
        newShape.value = saveMask;
        return;
      }
      event.preventDefault();
      event.stopImmediatePropagation();
      if (hasPendingKeyframe.value) confirmPendingKeyframe();
      const saveShape = finalizeTrackingSession();
      if (saveShape) newShape.value = saveShape;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      if (isVos) {
        event.stopImmediatePropagation();
        resetSmartTracking();
        return;
      }
      cancelTrackingSession();
    }
  };

  // ─── Tracking: discard pending edit on frame change ─────────────────────

  $effect(() => {
    const currentFrame = currentFrameIndex.value;
    const pendingFrame = pendingKeyframeIndex.value;
    if (pendingFrame !== null && pendingFrame !== currentFrame) {
      untrack(() => discardPendingKeyframe());
    }
  });

  // ─── Tracking: cancel on tool switch away from Rectangle ──────────────────

  $effect(() => {
    const toolType = selectedTool.value?.type;
    if (isTracking.value && toolType !== ToolType.Rectangle) {
      untrack(() => cancelTrackingSession());
    }
  });

  $effect(() => {
    const toolType = selectedTool.value?.type;
    if (
      !shouldClearVideoMaskSessionOnToolSwitch(toolType, {
        isVosSessionActive: isVosSessionActive.value,
        hasTracker: sam2Tracker !== null,
        hasActiveJob: activeVosJob !== null,
      })
    )
      return;

    untrack(() => {
      resetSmartTracking();
    });
  });

  $effect(() => {
    void selectedVideoSegmentationModel.value;
    untrack(() => {
      resetSmartTracking();
    });
  });

  $effect(() => {
    const shape = newShape.value;
    if (shape.status !== "none" || !shape.shouldReset) return;

    untrack(() => {
      const resetAction = resolveVideoMaskResetAction(shape, {
        isVosSessionActive: isVosSessionActive.value,
        hasTracker: sam2Tracker !== null,
        hasActiveJob: activeVosJob !== null,
      });
      if (resetAction === "reset-smart-tracking") {
        resetSmartTracking();
      } else if (resetAction === "clear-preview") {
        clearSmartPreview(shape.resetViewRef?.name);
        resetSmartSegmentationFeedback();
      }
      consumeResetStateOnNextMicrotask(shape);
    });
  });

  $effect(() => {
    const toolType = selectedTool.value?.type;
    const tracker = sam2Tracker;
    const frameIndex = currentFrameIndex.value;
    const anchor = vosSession.value.anchor;
    const activeViewName = anchor?.viewRef.name ?? tracker?.viewName ?? null;
    if (
      !shouldHydrateVideoPreview(toolType, {
        isVosSessionActive: isVosSessionActive.value,
        hasTracker: tracker !== null,
        hasActiveJob: activeVosJob !== null,
      })
    ) {
      if (activeViewName) {
        untrack(() => {
          clearSmartPreview(activeViewName);
        });
      }
      return;
    }
    if (!activeViewName) return;

    const interpolated = tracker?.interpolateAt(frameIndex) ?? null;
    if (interpolated) {
      setSmartPreview(activeViewName, interpolated.data.mask);
      return;
    }

    if (anchor && anchor.viewRef.name === activeViewName && anchor.frameIndex === frameIndex) {
      setSmartPreview(activeViewName, anchor.mask);
      return;
    }

    clearSmartPreview(activeViewName);
  });
</script>

<svelte:window onkeydown={handleTrackingKeydown} />

<section
  class="h-full w-full flex flex-col"
  onmouseup={() => {
    expanding = false;
  }}
  onmousemove={expand}
  role="tab"
  tabindex="0"
>
  <div class="overflow-hidden grow relative">
    {#if !isRouteLoading && isLoaded && current_itemBBoxes.value && current_itemKeypoints.value}
      <Canvas2D
        confirmKeys={["t", "T"]}
        selectedItemId={selectedItem.item.id}
        imagesPerView={imagesPerView.value}
        colorScale={colorScale.value[1]}
        bboxes={mergedBBoxes}
        masks={current_itemMasks.value}
        multiPaths={current_itemMultiPaths.value}
        keypoints={current_itemKeypoints.value}
        canvasSize={inspectorMaxHeight + resize}
        enableRenderCache={false}
        isPlaybackActive={playbackState.value.intervalId !== 0}
        imageSmoothing={imageSmoothing.value}
        selectedTool={selectedTool.value}
        brushSettings={brushSettings.value}
        newShape={newShape.value}
        {smartPreviewMasks}
        smartInferenceStatus={smartSegmentationUiState.value}
        showSmartPromptCursorOverlay={true}
        {currentSequenceFrameRefsByView}
        onSelectedToolChange={(tool: SelectionTool) => {
          selectedTool.value =
            tool.type === ToolType.InteractiveSegmenter
              ? { ...vosTool, promptMode: tool.promptMode }
              : tool;
        }}
        onNewShapeChange={(shape) => {
          handleCanvasShapeChange(shape as import("$lib/ui").Shape);
        }}
        onBrushSettingsChange={(settings: BrushSettings) => {
          brushSettings.value = settings;
        }}
        onAIRequest={(requestId, request) => {
          void handleSmartSegmentationRequest(requestId, request);
        }}
        {merge}
      />
      {#if playbackState.value.isBuffering}
        <div class="absolute inset-0 z-10 flex items-center justify-center pointer-events-none">
          <AiProcessingBadge message="Buffering next frames..." />
        </div>
      {/if}
      {#if isTracking.value}
        <div
          class="absolute top-2 left-1/2 -translate-x-1/2 z-20 rounded bg-amber-600/90 px-3 py-1 text-xs text-white shadow pointer-events-none select-none"
        >
          {#if hasPendingKeyframe.value}
            Drag to adjust &middot; Press T to confirm as keyframe &middot; Navigate away to discard
          {:else if isAwaitingNewSegmentKeyframe.value}
            New segment started &middot; Navigate to a frame and draw a bbox to begin
          {:else}
            Draw or edit on a frame and press T &middot; N for new segment &middot; Enter to save
            &middot; Escape to cancel
          {/if}
        </div>
      {/if}
      {#if selectedTool.value?.type === ToolType.VOS}
        <div
          class="absolute top-2 left-1/2 -translate-x-1/2 z-20 rounded bg-amber-600/90 px-3 py-1 text-xs text-white shadow pointer-events-none select-none"
        >
          {#if smartSegmentationUiState.value.phase === "pending"}
            Tracking interval... Scrub is locked until the request finishes
          {:else if vosAnchorFrameIndex.value === null}
            Prompt an object to set anchor A &middot; Scrub forward and press T &middot; N starts a
            new segment &middot; Enter saves &middot; Escape resets
          {:else}
            Anchor at frame #{vosAnchorFrameIndex.value} &middot; Scrub forward and press T &middot;
            N starts a new segment &middot; Enter saves &middot; Escape resets
          {/if}
        </div>
      {/if}
    {:else}
      <div class="h-full w-full bg-canvas flex items-center justify-center">
        <AiProcessingBadge message="Loading video frames..." />
      </div>
    {/if}
  </div>
  {#if !isRouteLoading && isLoaded && current_itemBBoxes.value && current_itemKeypoints.value}
    <button
      type="button"
      aria-label="Resize canvas and inspector panels"
      class="h-1 bg-primary-light cursor-row-resize w-full"
      onmousedown={() => {
        expanding = true;
      }}
    ></button>
    <div
      class="h-full grow max-h-[28%] overflow-hidden border-t border-border/40 bg-card/90"
      style={`max-height: ${inspectorMaxHeight}px`}
    >
      <TimelinePanel />
    </div>
  {/if}
</section>
