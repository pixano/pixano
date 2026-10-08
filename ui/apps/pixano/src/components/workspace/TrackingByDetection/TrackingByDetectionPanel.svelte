<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Binoculars, X } from "phosphor-svelte";

  import {
    acceptTrackingByDetection,
    resolveWorkspaceLabelField,
  } from "./trackingByDetectionAccept";
  import { currentItemSaveCoordinator } from "$lib/stores/appStores.svelte";
  import {
    inferenceServerStore,
    selectedTrackingByDetectionModel,
    trackingByDetectionModels,
  } from "$lib/stores/inferenceStores.svelte";
  import {
    cancelTrackingByDetectionRun,
    detectionTrackColorById,
    detectionTrackEntityId,
    keptDetectionTracks,
    openTrackingByDetectionSetup,
    resetTrackingByDetectionSession,
    resolveTrackingFrameSources,
    selectDetectionTrack,
    selectTrackingByDetectionView,
    setDetectionReviewThreshold,
    startTrackingByDetectionRunHere,
    toggleDetectionTrackDiscard,
    trackingByDetectionRowEstimate,
    trackingByDetectionSession,
    updateTrackingByDetectionParams,
    visibleDetectionTracks,
  } from "$lib/stores/trackingByDetectionStore.svelte";
  import { currentFrameIndex, playbackState, videoViewNames } from "$lib/stores/videoStores.svelte";
  import { parseClassList, resolveTrackingWindow } from "$lib/tracking/trackingByDetection";
  import { getInferenceModelKey, isSameInferenceModel } from "$lib/types/inference";
  import { AiProcessingBadge, cn, IconButton, ModelSelectBadge } from "$lib/ui";
  import { updateView } from "$lib/utils/videoOperations";
  import { getWorkspaceContext } from "$lib/workspace/context";

  const workspace = getWorkspaceContext();

  const session = $derived(trackingByDetectionSession.value);
  const models = $derived(trackingByDetectionModels.value);
  const selectedModel = $derived(
    models.find((model) => isSameInferenceModel(model, selectedTrackingByDetectionModel.value)) ??
      null,
  );
  const modelClassNames = $derived(selectedModel?.interface?.class_names ?? null);
  const window = $derived.by(() => {
    if (!session.viewName) return null;
    return resolveTrackingWindow(
      resolveTrackingFrameSources(session.viewName),
      session.params.fromCurrentFrame ? currentFrameIndex.value : null,
    );
  });
  const estimate = $derived(trackingByDetectionRowEstimate.value);
  const labelField = $derived(resolveWorkspaceLabelField(workspace.manifest));
  const isPlaying = $derived(playbackState.value.intervalId !== 0);
  const discarded = $derived(new Set(session.discardedTrackIds));
  const keptCount = $derived(keptDetectionTracks.value.length);
  const modelLabel = $derived.by(() => {
    if (selectedModel) return selectedModel.name;
    if (inferenceServerStore.value.status === "loading") return "Loading";
    if (!inferenceServerStore.value.connected) return "No server";
    return "No tracking-by-detection model";
  });

  let classText = $state("");

  function selectModel(key: string): void {
    const model = models.find((candidate) => getInferenceModelKey(candidate) === key);
    if (model) selectedTrackingByDetectionModel.value = model;
  }

  function toggleClass(name: string): void {
    const classes = session.params.classes.includes(name)
      ? session.params.classes.filter((value) => value !== name)
      : [...session.params.classes, name];
    updateTrackingByDetectionParams({ classes });
  }

  function commitClassText(): void {
    updateTrackingByDetectionParams({ classes: parseClassList(classText) });
  }

  function run(): void {
    if (!selectedModel || !window) return;
    void startTrackingByDetectionRunHere(selectedModel);
  }

  function jumpTo(trackId: number, frameIndex: number): void {
    selectDetectionTrack(trackId);
    if (currentFrameIndex.value !== frameIndex) {
      currentFrameIndex.value = frameIndex;
      updateView(frameIndex);
    }
  }

  /** Back to the form with the same target; the parameters are kept. */
  function runAgain(): void {
    if (session.target && session.viewName) {
      openTrackingByDetectionSetup(session.target, session.viewName);
    }
  }

  function accept(): void {
    const accepted = acceptTrackingByDetection({
      manifest: workspace.manifest,
      featureValues: workspace.featureValues,
    });
    if (accepted) void currentItemSaveCoordinator.requestSave();
  }

  function percent(value: number): string {
    return `${Math.round(value * 100)}%`;
  }

  const buttonClass =
    "rounded-lg border px-3 py-1.5 text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50";
  const primaryButtonClass = cn(
    buttonClass,
    "border-primary/60 bg-primary text-primary-foreground hover:bg-primary/90",
  );
  const secondaryButtonClass = cn(
    buttonClass,
    "border-border/60 bg-background text-foreground hover:bg-muted/60",
  );
</script>

<div class="flex h-full flex-col overflow-hidden">
  <div class="flex shrink-0 items-center gap-2 border-b border-border/50 px-3 py-2">
    <Binoculars class="h-4 w-4 text-primary" />
    <span class="flex-1 text-xs font-semibold">Track objects by detection</span>
    <IconButton tooltipContent="Close" onclick={resetTrackingByDetectionSession} class="h-7 w-7">
      <X class="h-3.5 w-3.5" />
    </IconButton>
  </div>

  <div class="min-h-0 flex-1 overflow-y-auto px-3 py-3 text-xs">
    {#if session.phase === "setup" || session.phase === "error"}
      {#if session.phase === "error" && session.error}
        <p
          class="mb-3 rounded-md border border-destructive/40 bg-destructive/10 px-2 py-1.5 text-destructive"
        >
          {session.error}
        </p>
      {/if}

      <div class="flex flex-col gap-3">
        <label class="flex flex-col gap-1">
          <span class="font-medium text-muted-foreground">Model</span>
          <ModelSelectBadge
            {models}
            selectedModelKey={selectedModel ? getInferenceModelKey(selectedModel) : ""}
            disabled={models.length === 0}
            label={modelLabel}
            onValueChange={selectModel}
          />
        </label>

        {#if videoViewNames.value.length > 1}
          <label class="flex flex-col gap-1">
            <span class="font-medium text-muted-foreground">View</span>
            <select
              class="rounded-md border border-border/60 bg-background px-2 py-1"
              value={session.viewName ?? ""}
              onchange={(event) => selectTrackingByDetectionView(event.currentTarget.value)}
            >
              {#each videoViewNames.value as viewName (viewName)}
                <option value={viewName}>{viewName}</option>
              {/each}
            </select>
          </label>
        {/if}

        <div class="flex flex-col gap-1">
          <span class="font-medium text-muted-foreground">
            Classes <span class="font-normal">(none: the model's own set)</span>
          </span>
          {#if modelClassNames && modelClassNames.length > 0}
            <div class="flex flex-wrap gap-1">
              {#each modelClassNames as name (name)}
                <button
                  type="button"
                  class={cn(
                    "rounded-full border px-2 py-0.5 text-[11px] transition-colors",
                    session.params.classes.includes(name)
                      ? "border-primary/60 bg-primary/15 text-foreground"
                      : "border-border/50 bg-background text-muted-foreground hover:bg-muted/50",
                  )}
                  onclick={() => toggleClass(name)}
                >
                  {name}
                </button>
              {/each}
            </div>
          {:else}
            <input
              type="text"
              class="rounded-md border border-border/60 bg-background px-2 py-1"
              placeholder="person, car"
              bind:value={classText}
              onchange={commitClassText}
            />
          {/if}
        </div>

        <label class="flex flex-col gap-1">
          <span class="font-medium text-muted-foreground">
            Detection threshold · {percent(session.params.boxThreshold)}
          </span>
          <input
            type="range"
            min="0"
            max="1"
            step="0.01"
            value={session.params.boxThreshold}
            oninput={(event) =>
              updateTrackingByDetectionParams({ boxThreshold: Number(event.currentTarget.value) })}
          />
        </label>

        <label class="flex items-center gap-2">
          <input
            type="checkbox"
            checked={session.params.fromCurrentFrame}
            onchange={(event) =>
              updateTrackingByDetectionParams({ fromCurrentFrame: event.currentTarget.checked })}
          />
          <span>From the current frame</span>
          {#if window}
            <span class="text-muted-foreground">
              #{window.startFrameIndex} → #{window.endFrameIndex} ({window.frameCount} frames)
            </span>
          {/if}
        </label>

        <label class="flex items-center gap-2">
          <span class="font-medium text-muted-foreground">Keep a box every</span>
          <input
            type="number"
            min="1"
            class="w-16 rounded-md border border-border/60 bg-background px-2 py-1"
            value={session.params.keyframeStride}
            onchange={(event) =>
              updateTrackingByDetectionParams({
                keyframeStride: Math.max(1, Math.floor(Number(event.currentTarget.value) || 1)),
              })}
          />
          <span class="text-muted-foreground">frames (the rest is interpolated)</span>
        </label>

        <div class="flex gap-2 pt-1">
          <button
            type="button"
            class={primaryButtonClass}
            disabled={!selectedModel || !window}
            onclick={run}
          >
            Run
          </button>
          <button
            type="button"
            class={secondaryButtonClass}
            onclick={resetTrackingByDetectionSession}
          >
            Cancel
          </button>
        </div>
      </div>
    {:else if session.phase === "running"}
      <div class="flex flex-col items-center gap-3 py-6">
        <AiProcessingBadge message="Detecting and tracking..." />
        {#if session.run}
          <p class="text-muted-foreground">
            {session.run.model} · frames #{session.run.startFrameIndex} → #{session.run
              .endFrameIndex} ({session.run.frameCount})
          </p>
        {/if}
        <button
          type="button"
          class={secondaryButtonClass}
          onclick={() => void cancelTrackingByDetectionRun()}
        >
          Cancel
        </button>
      </div>
    {:else if session.phase === "review"}
      <div class="flex flex-col gap-3">
        <p class="font-medium">
          {visibleDetectionTracks.value.length} track{visibleDetectionTracks.value.length === 1
            ? ""
            : "s"} · {keptCount} kept
        </p>

        <label class="flex flex-col gap-1">
          <span class="font-medium text-muted-foreground">
            Mean score at least {percent(session.reviewThreshold)}
          </span>
          <input
            type="range"
            min={session.params.boxThreshold}
            max="1"
            step="0.01"
            value={session.reviewThreshold}
            oninput={(event) => setDetectionReviewThreshold(Number(event.currentTarget.value))}
          />
        </label>

        {#if session.skipped.noBox > 0 || session.skipped.unknownFrame > 0}
          <p class="text-muted-foreground">
            Ignored: {session.skipped.noBox} object{session.skipped.noBox === 1 ? "" : "s"} without a
            box, {session.skipped.unknownFrame} outside the frame window.
          </p>
        {/if}

        <ul class="flex flex-col gap-0.5">
          {#each visibleDetectionTracks.value as track (track.trackId)}
            {@const isDiscarded = discarded.has(track.trackId)}
            {@const isSelected = session.selectedTrackId === track.trackId}
            <li
              class={cn(
                "flex items-center gap-2 rounded-md px-1.5 py-1 transition-colors",
                isSelected ? "bg-primary/10 ring-1 ring-primary/40" : "hover:bg-muted/40",
                { "opacity-50": isDiscarded },
              )}
            >
              <input
                type="checkbox"
                checked={!isDiscarded}
                aria-label={`Keep ${track.className ?? "object"} #${track.trackId}`}
                onchange={() => toggleDetectionTrackDiscard(track.trackId)}
              />
              <button
                type="button"
                class="flex min-w-0 flex-1 items-center gap-2 text-left"
                onclick={() => jumpTo(track.trackId, track.startFrame)}
              >
                <span
                  class="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={`background: ${detectionTrackColorById.value.get(detectionTrackEntityId(track.trackId)) ?? "currentColor"}`}
                ></span>
                <span class="truncate font-medium">
                  {track.className ?? "object"} #{track.trackId}
                </span>
                <span class="ml-auto shrink-0 tabular-nums text-muted-foreground">
                  #{track.startFrame}–#{track.endFrame} · {track.detectionCount} · {percent(
                    track.meanScore,
                  )}
                </span>
              </button>
            </li>
          {/each}
        </ul>

        <p class="text-muted-foreground">
          Accept creates {estimate.entities} object{estimate.entities === 1 ? "" : "s"},
          {estimate.tracklets} tracklet{estimate.tracklets === 1 ? "" : "s"} and {estimate.bboxes}
          box{estimate.bboxes === 1 ? "" : "es"}
          {#if labelField}
            (class in <code>{labelField}</code>
            )
          {:else}
            (class kept in the provenance: this dataset's objects have no label field)
          {/if}
          {#if estimate.bboxes > 1500}
            — large: raise "keep a box every N frames" and run again to save fewer rows.
          {/if}
        </p>

        <div class="flex flex-wrap gap-2 pt-1">
          <button
            type="button"
            class={primaryButtonClass}
            disabled={keptCount === 0 || isPlaying}
            title={isPlaying ? "Pause the video first" : undefined}
            onclick={accept}
          >
            Accept kept ({keptCount})
          </button>
          <button
            type="button"
            class={secondaryButtonClass}
            onclick={resetTrackingByDetectionSession}
          >
            Discard all
          </button>
          <button type="button" class={secondaryButtonClass} onclick={runAgain}>Run again</button>
        </div>
      </div>
    {/if}
  </div>
</div>
