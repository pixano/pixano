# Implementation Plan: Targeted Interval Tracking (VOS) with SAM2/SAM3

## Objective
Implement a "Targeted Interval Tracking" workflow for Video Object Segmentation (VOS) in the Pixano video workspace, allowing users to leverage powerful AI models like SAM2/SAM3 without overwhelming inference servers or browser memory.

## Background & Motivation
SAM2 and SAM3 introduce a paradigm shift from manual frame-by-frame interpolation to AI-driven temporal mask propagation. To manage compute costs and maintain user control, we are adopting a "bracketed" approach: the user defines a start frame (A) with a prompt, scrubs to an end frame (B), and triggers tracking explicitly for that interval.

## Scope & Impact
*   **Stores**: Extending `src/lib/stores/trackingStore.svelte.ts` to support VOS interval states without creating new stores.
*   **Tools**: Defining a generic `ToolType.VOS` to separate logic from standard interactive segmentation and bbox tracking.
*   **Engine**: Updating `Sam2VideoTracker` (and standardizing a generic API) to handle interval-based propagation.
*   **UI**: Updating `WorkspaceVideo.svelte` to handle `T` (Track), `N` (New Segment), and `Enter` (Finalize) specifically for the VOS tool, plus timeline visualizations for pending intervals.

## Proposed Solution & Architecture

### 1. Generic VOS API Design
To support SAM2/SAM3 (which require loading a video state, adding prompts to specific frames, and propagating) as well as future models, we will standardize the tracking API payload.

**Endpoint Draft:** `POST /api/v1/inference/track_interval`
```typescript
interface VOSTrackIntervalRequest {
  datasetId: string;
  itemId: string;
  viewName: string;
  model: string;
  interval: {
    startFrame: number;
    endFrame: number;
    direction: "forward" | "backward";
  };
  keyframes: Array<{
    frameIndex: number;
    prompts: {
      points?: Array<{ x: number, y: number, label: 0 | 1 }>;
      box?: { x: number, y: number, width: number, height: number };
      mask?: SaveMaskShape; // For manual brush corrections
    };
  }>;
}
```
*Why this works for SAM2/3:* The server can instantiate `init_state` for the video, map the `keyframes` using `add_new_points_or_box` / `add_new_mask`, and run `propagate_in_video` up to the `endFrame`.

### 2. State Management (`trackingStore.svelte.ts`)
We will extend the existing tracking store to handle VOS intervals.

```typescript
// New state variables to add to trackingStore
export const vosStartKeyframeIndex = $state<number | null>(null);
export const isVosSessionActive = $derived(vosStartKeyframeIndex.value !== null);
export const vosPendingInterval = $derived<[number, number] | null>(() => {
    if (vosStartKeyframeIndex.value === null) return null;
    return [vosStartKeyframeIndex.value, currentFrameIndex.value];
});
```

### 3. Component Wiring (`WorkspaceVideo.svelte`)
We will intercept the keyboard shortcuts when the VOS tool is active.

*   **Prompting (Click/Box):** User interacts on Frame A. It acts exactly like the static `InteractiveSegmenter` (fetching a single-frame preview) but also sets `vosStartKeyframeIndex = A`.
*   **`T` (Track):** User scrubs to Frame B and presses `T`.
    *   Checks if `vosStartKeyframeIndex` is set.
    *   Calls `sam2Tracker.propagateInterval(start, current)`.
    *   Displays a loading overlay.
    *   Sets `vosStartKeyframeIndex = currentFrameIndex` (making B the new anchor for further tracking).
*   **`N` (New Segment):** Handles occlusion.
    *   Clears `vosStartKeyframeIndex`.
    *   Allows the user to scrub forward and start a completely new tracklet (by dropping a new point) without connecting it to the previous frames.
*   **Timeline UI:** We will pass `vosPendingInterval` to `TimelinePanel.svelte`. If it's not null, the timeline will render a ghosted/striped block between `start` and `current` to indicate the pending compute bracket.

### 4. Engine Updates (`src/lib/trackers/Sam2VideoTracker.ts`)
We will add the interval propagation method.

```typescript
class Sam2VideoTracker {
  // ... existing code ...

  async propagateInterval(
    startFrame: number,
    endFrame: number,
    keyframes: VOSKeyframe[]
  ): Promise<TrackingOutput[]> {
    // 1. Construct VOSTrackIntervalRequest
    // 2. Call the inference API
    // 3. Store the returned RLE masks internally to prevent browser memory bloat
    // 4. Update the UI's smartPreviewMasks for the current timeline view
  }
}
```

## Alternatives Considered
*   **Open-ended tracking (Play to track):** Rejected because it risks runaway server compute if the user forgets to stop, and wastes resources if the model drifts early but compute continues for 200 frames.
*   **Separate `vosStore.svelte.ts`:** Rejected to avoid store bloat. VOS is a form of tracking, so keeping it in `trackingStore` is more cohesive, even if we add a few VOS-specific state variables.

## Implementation Steps
1.  **Define Tool:** Add `ToolType.VOS` to `src/lib/tools` and update toolbar UI to allow selecting it.
2.  **Update State:** Add `vosStartKeyframeIndex` and interval logic to `trackingStore.svelte.ts`.
3.  **Upgrade Engine:** Implement `propagateInterval` in `Sam2VideoTracker.ts` to format and send the new generic API payload.
4.  **Wire Shortcuts:** Update `handleTrackingKeydown` in `WorkspaceVideo.svelte` to execute the VOS logic (`T`, `N`, `Enter`) when `ToolType.VOS` is active.
5.  **UI Feedback:** Update `TimelinePanel.svelte` to accept and render the pending interval visually.

## Verification
*   **State transitions:** Ensure that switching away from the VOS tool safely cancels any pending intervals.
*   **API Payload:** Verify that the `interval.startFrame` and `interval.endFrame` correctly respect the user's scrubbing direction (forward or backward tracking).
*   **Memory:** Ensure that tracking a 300-frame interval does not cause a massive spike in Svelte's reactivity engine by keeping the historical masks isolated from `$state` unless currently being rendered.
