<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { CircleNotch, Pause, Play, SkipBack, SkipForward } from "phosphor-svelte";

  import { currentFrameIndex, lastFrameIndex, playbackState } from "$lib/stores/videoStores.svelte";
  import {
    ensureFrameAvailable,
    getReadyAheadFrames,
    isFrameReady,
    primePlaybackPrefetch,
    updateViewAndWait,
    waitForReadyAheadFrames,
  } from "$lib/utils/videoOperations";

  interface Props {
    resetHighlight: () => void;
  }

  let { resetHighlight }: Props = $props();
  let playbackTransitionInFlight = false;
  let bufferingToken = 0;
  let shouldResumeAfterBuffering = false;

  const LOW_BUFFER_SECONDS = 0.8;
  const HIGH_BUFFER_SECONDS = 2.5;
  const MIN_LOW_BUFFER_FRAMES = 2;
  const MIN_HIGH_BUFFER_FRAMES = 8;
  const MAX_LOW_BUFFER_FRAMES = 120;
  const MAX_HIGH_BUFFER_FRAMES = 240;
  const BUFFERING_UI_DELAY_MS = 180;
  const BUFFERING_MIN_VISIBLE_MS = 180;

  const getBufferWatermarks = (): { lowFrames: number; highFrames: number } => {
    const frameDurationMs = Math.max(playbackState.value.videoSpeed, 1);
    const lowFrames = Math.min(
      MAX_LOW_BUFFER_FRAMES,
      Math.max(MIN_LOW_BUFFER_FRAMES, Math.round((LOW_BUFFER_SECONDS * 1000) / frameDurationMs)),
    );
    const highFrames = Math.min(
      MAX_HIGH_BUFFER_FRAMES,
      Math.max(
        MIN_HIGH_BUFFER_FRAMES,
        lowFrames + 1,
        Math.round((HIGH_BUFFER_SECONDS * 1000) / frameDurationMs),
      ),
    );
    return { lowFrames, highFrames };
  };

  $effect(() => {
    return () => {
      clearInterval(playbackState.value.intervalId);
      bufferingToken += 1;
      shouldResumeAfterBuffering = false;
    };
  });

  const stopPlayback = (clearResumeIntent = false) => {
    clearInterval(playbackState.value.intervalId);
    playbackState.update((old) => ({ ...old, intervalId: 0 }));
    if (clearResumeIntent) {
      shouldResumeAfterBuffering = false;
    }
  };

  const setBuffering = (isBuffering: boolean) => {
    playbackState.update((old) => ({ ...old, isBuffering }));
  };

  const wait = (durationMs: number) =>
    new Promise<void>((resolve) => {
      setTimeout(resolve, durationMs);
    });

  const awaitWithBufferingIndicator = async (
    token: number,
    task: () => Promise<boolean>,
  ): Promise<boolean> => {
    let shownAt = 0;
    let isShown = false;

    const timer = setTimeout(() => {
      if (token !== bufferingToken) return;
      shownAt = Date.now();
      isShown = true;
      setBuffering(true);
    }, BUFFERING_UI_DELAY_MS);

    try {
      return await task();
    } finally {
      clearTimeout(timer);
      if (isShown && token === bufferingToken) {
        const visibleFor = Date.now() - shownAt;
        if (visibleFor < BUFFERING_MIN_VISIBLE_MS) {
          await wait(BUFFERING_MIN_VISIBLE_MS - visibleFor);
        }
        if (token === bufferingToken) {
          setBuffering(false);
        }
      }
    }
  };

  const cancelBuffering = () => {
    bufferingToken += 1;
    shouldResumeAfterBuffering = false;
    setBuffering(false);
  };

  const goToFrame = async (target: number): Promise<boolean> => {
    const max = lastFrameIndex.value;
    if (max === undefined) return false;
    if (target < 0 || target > max) return false;

    primePlaybackPrefetch(target);
    const instantlyReady = isFrameReady(target);

    if (!instantlyReady) {
      stopPlayback();
      const token = ++bufferingToken;
      const available = await awaitWithBufferingIndicator(token, () =>
        ensureFrameAvailable(target),
      );
      if (token !== bufferingToken) return false;
      if (!available) return false;
    }

    currentFrameIndex.value = target;
    const rendered = await updateViewAndWait(target);
    return rendered;
  };

  const pauseForBufferingIfNeeded = async (): Promise<boolean> => {
    const max = lastFrameIndex.value;
    if (max === undefined) return false;

    const current = currentFrameIndex.value;
    if (current >= max) return true;

    primePlaybackPrefetch(current);

    const remaining = max - current;
    const { lowFrames, highFrames } = getBufferWatermarks();
    const effectiveLow = Math.min(lowFrames, remaining);
    const effectiveHigh = Math.min(highFrames, remaining);

    const readyAhead = getReadyAheadFrames(current, effectiveHigh);
    if (readyAhead >= effectiveLow) {
      return true;
    }

    stopPlayback();
    const token = ++bufferingToken;
    const buffered = await awaitWithBufferingIndicator(token, () =>
      waitForReadyAheadFrames(current, effectiveHigh),
    );
    if (token !== bufferingToken) return false;

    if (buffered && shouldResumeAfterBuffering) {
      playVideo();
    }
    return false;
  };

  const playVideo = () => {
    if (!playbackState.value.isLoaded || playbackState.value.isBuffering) return;

    shouldResumeAfterBuffering = true;
    stopPlayback();
    const interval = setInterval(() => {
      if (playbackTransitionInFlight) return;

      playbackTransitionInFlight = true;
      void (async () => {
        const canContinue = await pauseForBufferingIfNeeded();
        if (!canContinue) return;

        const max = lastFrameIndex.value;
        if (max === undefined) return;

        if (currentFrameIndex.value >= max) {
          stopPlayback(true);
          return;
        }
        const rendered = await goToFrame(currentFrameIndex.value + 1);
        if (!rendered) {
          stopPlayback(true);
          return;
        }
        if (playbackState.value.intervalId === 0 && shouldResumeAfterBuffering) {
          playVideo();
        }
      })().finally(() => {
        playbackTransitionInFlight = false;
      });
    }, playbackState.value.videoSpeed);

    playbackState.update((old) => ({ ...old, intervalId: Number(interval), isBuffering: false }));
  };

  const onPlayStepClick = () => {
    resetHighlight();
    if (playbackState.value.intervalId) {
      stopPlayback(true);
    } else {
      if (!playbackState.value.isLoaded) return;
      cancelBuffering();
      void goToFrame(currentFrameIndex.value + 1);
    }
  };

  const onPlayStepBackClick = () => {
    resetHighlight();
    if (playbackState.value.intervalId) {
      stopPlayback(true);
    } else {
      if (!playbackState.value.isLoaded) return;
      cancelBuffering();
      void goToFrame(currentFrameIndex.value - 1);
    }
  };

  const onPlayClick = () => {
    resetHighlight();
    if (playbackState.value.intervalId || playbackState.value.isBuffering) {
      stopPlayback(true);
      cancelBuffering();
    } else {
      const max = lastFrameIndex.value;
      if (max !== undefined && currentFrameIndex.value >= max) return;
      playVideo();
    }
  };

  function shortcutHandler(event: KeyboardEvent) {
    const activeElement = document.activeElement;
    if (
      activeElement instanceof HTMLInputElement ||
      activeElement instanceof HTMLTextAreaElement ||
      activeElement?.getAttribute("contenteditable") === "true"
    ) {
      return; // Ignore shortcut when typing text
    }

    switch (event.code) {
      case "Space":
        if (event.repeat) break;
        event.preventDefault();
        onPlayClick();
        break;
      case "ArrowRight":
      case "KeyD":
        if (event.shiftKey) break;
        onPlayStepClick();
        break;
      case "ArrowLeft":
      case "KeyA":
        if (event.shiftKey) break;
        onPlayStepBackClick();
        break;
    }
  }
</script>

<div class="flex items-center gap-1.5">
  <button
    title={playbackState.value.isBuffering
      ? "Buffering..."
      : playbackState.value.intervalId
        ? "Pause (space)"
        : "Play (space)"}
    onclick={onPlayClick}
    class="inline-flex h-7 w-7 items-center justify-center rounded-md border border-border/50 bg-background/80 text-primary transition-colors hover:border-primary/30 hover:bg-accent/80 disabled:pointer-events-none disabled:opacity-40"
  >
    {#if playbackState.value.isBuffering}
      <CircleNotch weight="regular" class="h-4 w-4 animate-spin" />
    {:else if playbackState.value.intervalId}
      <Pause weight="fill" class="h-4 w-4" />
    {:else}
      <Play weight="fill" class="ml-0.5 h-4 w-4" />
    {/if}
  </button>
  <button
    title="Previous frame (Left / A or Q)"
    onclick={onPlayStepBackClick}
    class="inline-flex h-7 w-7 items-center justify-center rounded-md border border-border/50 bg-background/80 text-primary transition-colors hover:border-primary/30 hover:bg-accent/80"
  >
    <SkipBack weight="fill" class="h-4 w-4" />
  </button>
  <button
    title="Next frame (Right / D)"
    onclick={onPlayStepClick}
    class="inline-flex h-7 w-7 items-center justify-center rounded-md border border-border/50 bg-background/80 text-primary transition-colors hover:border-primary/30 hover:bg-accent/80"
  >
    <SkipForward weight="fill" class="h-4 w-4" />
  </button>
</div>
<svelte:window onkeydown={shortcutHandler} />
