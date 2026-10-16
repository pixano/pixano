<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import {
    CircleNotch,
    Pause,
    Play,
    Repeat,
    SkipBack,
    SkipBackCircle,
    SkipForward,
  } from "phosphor-svelte";

  import { currentFrameIndex, lastFrameIndex, playbackState } from "$lib/stores/videoStores.svelte";
  import { IconButton } from "$lib/ui";
  import { cn } from "$lib/utils/styleUtils";
  import {
    ensureFrameAvailable,
    getReadyAheadFrames,
    isFrameReady,
    primePlaybackPrefetch,
    updateViewAndWait,
    waitForReadyAheadFrames,
  } from "$lib/utils/videoOperations";
  import { homeShortcutIsTaken, resolveNextPlaybackFrame } from "$lib/utils/videoPlayback";

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

        const step = resolveNextPlaybackFrame(
          currentFrameIndex.value,
          max,
          playbackState.value.loop,
        );
        if (step.action === "stop") {
          stopPlayback(true);
          return;
        }
        const rendered = await goToFrame(step.frame);
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
      const atEnd = max !== undefined && currentFrameIndex.value >= max;
      if (atEnd && !playbackState.value.loop) return;
      if (atEnd) {
        // Looping from the last frame: show frame 0 before the interval starts.
        void goToFrame(0).then((rendered) => {
          if (rendered) playVideo();
        });
        return;
      }
      playVideo();
    }
  };

  const onFirstFrameClick = () => {
    resetHighlight();
    if (playbackState.value.intervalId) {
      stopPlayback(true);
    } else {
      if (!playbackState.value.isLoaded) return;
      cancelBuffering();
    }
    void goToFrame(0);
  };

  const toggleLoop = () => {
    playbackState.update((old) => ({ ...old, loop: !old.loop }));
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
      case "Home":
        if (homeShortcutIsTaken(event)) break;
        event.preventDefault();
        onFirstFrameClick();
        break;
    }
  }
</script>

<div class="flex items-center gap-1.5">
  <IconButton
    tooltipContent={playbackState.value.isBuffering
      ? "Buffering…"
      : playbackState.value.intervalId
        ? "Pause (Space)"
        : "Play (Space)"}
    onclick={onPlayClick}
    class="h-7 w-7 rounded-lg text-primary"
  >
    {#if playbackState.value.isBuffering}
      <CircleNotch weight="regular" class="h-4 w-4 animate-spin" />
    {:else if playbackState.value.intervalId}
      <Pause weight="fill" class="h-4 w-4" />
    {:else}
      <Play weight="fill" class="ml-0.5 h-4 w-4" />
    {/if}
  </IconButton>
  <IconButton
    tooltipContent="Previous frame (← / A)"
    onclick={onPlayStepBackClick}
    class="h-7 w-7 rounded-lg text-primary"
  >
    <SkipBack weight="fill" class="h-4 w-4" />
  </IconButton>
  <IconButton
    tooltipContent="Next frame (→ / D)"
    onclick={onPlayStepClick}
    class="h-7 w-7 rounded-lg text-primary"
  >
    <SkipForward weight="fill" class="h-4 w-4" />
  </IconButton>
  <IconButton
    tooltipContent="Go to first frame (Home)"
    onclick={onFirstFrameClick}
    class="h-7 w-7 rounded-lg text-primary"
  >
    <SkipBackCircle weight="fill" class="h-4 w-4" />
  </IconButton>
  <IconButton
    tooltipContent="Loop playback"
    onclick={toggleLoop}
    class={cn(
      "h-7 w-7 rounded-lg",
      playbackState.value.loop
        ? "bg-primary/20 text-primary hover:bg-primary/30"
        : "text-foreground hover:bg-accent",
    )}
  >
    <Repeat weight={playbackState.value.loop ? "fill" : "regular"} class="h-4 w-4" />
  </IconButton>
</div>
<svelte:window onkeydown={shortcutHandler} />
