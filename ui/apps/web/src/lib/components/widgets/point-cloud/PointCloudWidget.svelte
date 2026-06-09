<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Box, Eye, Globe, Move, MousePointer2, Orbit, Save, Scaling } from "lucide-svelte";
  import { getContext, onMount } from "svelte";
  import type { Component } from "svelte";

  import {
    buildBBox3DCreate,
    buildBBox3DUpdate,
    DEFAULT_3D_ROTATION,
    generateShortId,
  } from "$lib/annotations/buildPayloads.js";
  import type {
    DraftBBox3D,
    PointCloudWidgetStorage,
  } from "$lib/annotations/types.js";
  import type { LocalBBox3D } from "$lib/api/annotations.js";
  import type { WorkspaceManager } from "$lib/workspace/workspaceManager.svelte.js";

  import type { GizmoVisibility } from "./pointCloudTypes.js";

  interface Props {
    widgetId: string;
    options: Record<string, unknown>;
    data?: Record<string, unknown>;
  }

  let { widgetId, data }: Props = $props();

  const manager = getContext<WorkspaceManager>("workspaceManager");
  // svelte-ignore state_referenced_locally
  const stableWidgetId = widgetId;
  const storage = manager.getStorage(stableWidgetId) as PointCloudWidgetStorage;

  // svelte-ignore state_referenced_locally
  const datasetId = (data?.datasetId as string | undefined) ?? "";
  // svelte-ignore state_referenced_locally
  const recordId = (data?.recordId as string | undefined) ?? "";
  // svelte-ignore state_referenced_locally
  const viewId = (data?.viewId as string | undefined) ?? "";

  let cameraMode = $state<"orbit" | "first-person">("orbit");

  let confirmEditingId = $state<string | null>(null);
  // Clear persisted-box overrides when the record changes so stale edits don't bleed across records.
  $effect(() => { void data; storage.overrides = {}; });

  let ready = $state(false);
  let error = $state<string | null>(null);
  let CanvasComponent = $state<Component | null>(null);
  let SceneComponent = $state<Component | null>(null);
  let canvasEl = $state<HTMLDivElement | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let sceneRef = $state<any>(null);

  let confirmCoords = $state<[number, number, number, number, number, number] | null>(null);
  let confirmRotation = $state<number[] | undefined>(undefined);
  let gizmoVisibility = $state<GizmoVisibility>({ rings: true, resizeArrows: true, translateArrows: true });

  onMount(async () => {
    try {
      const [threlte, scene] = await Promise.all([
        import("@threlte/core"),
        import("./PointCloudScene.svelte"),
      ]);
      CanvasComponent = threlte.Canvas;
      SceneComponent = scene.default;
      ready = true;
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed to load 3D viewer";
    }
  });

  $effect(() => {
    if (!canvasEl) return;
    canvasEl.style.cursor = storage.mode === "draw-bbox3d" ? "crosshair" : "default";
  });

  function handleReadyToConfirm(
    coords: [number, number, number, number, number, number],
    rotation?: number[],
    editingId?: string,
  ): void {
    confirmEditingId = editingId ?? null;
    confirmCoords = coords;
    confirmRotation = rotation;
  }

  function handleDrawCanceled(): void {
    confirmCoords = null;
    confirmEditingId = null;
  }

  function handleConfirmSave(): void {
    if (!confirmCoords) return;
    const coords = confirmCoords;
    const rotation = confirmRotation;
    confirmCoords = null;

    if (confirmEditingId) {
      handleEditBoxSave(confirmEditingId, coords, rotation);
      confirmEditingId = null;
    } else {
      handleNewBoxSave(coords, rotation);
    }

    sceneRef?.reset();
  }

  function handleEditBoxSave(
    boxId: string,
    coords: [number, number, number, number, number, number],
    rotation: number[] | undefined,
  ): void {
    const existing = allBboxes3d.find((b) => b.id === boxId);
    if (!existing) return;

    const updateBody = buildBBox3DUpdate(
      { datasetId, recordId, viewId },
      boxId,
      existing.entity_id,
      coords,
      rotation,
    );
    const pending = manager.pendingMutations.find(
      (m) => m.op === "update" && m.resource === "bbox3ds" && m.id === boxId,
    );
    if (pending && pending.op === "update") {
      pending.body = updateBody;
    } else {
      manager.queueMutation({
        op: "update",
        resource: "bbox3ds",
        id: boxId,
        body: updateBody,
        widgetId: stableWidgetId,
        localBBoxId: boxId,
      });
    }
    const draftIdx = storage.drafts.findIndex((d) => d.id === boxId);
    if (draftIdx >= 0) {
      storage.drafts[draftIdx] = { ...storage.drafts[draftIdx], coordsLance: coords, rotation };
    } else {
      storage.overrides[boxId] = { coords, rotation };
    }
  }

  function handleNewBoxSave(
    coords: [number, number, number, number, number, number],
    rotation: number[] | undefined,
  ): void {
    const localId = generateShortId();
    const { entityId, mutations } = buildBBox3DCreate(
      { datasetId, recordId, viewId },
      coords,
      { widgetId: stableWidgetId, localBBoxId: localId, rotation },
    );
    const draft: DraftBBox3D = {
      id: localId,
      entityId,
      coordsLance: coords,
      rotation,
      persisted: false,
    };
    storage.drafts.push(draft);
    for (const m of mutations) {
      manager.queueMutation(m);
    }
  }

  function handleConfirmCancel(): void {
    confirmCoords = null;
    confirmEditingId = null;
    sceneRef?.reset();
  }

  const allBboxes3d = $derived<LocalBBox3D[]>([
    ...((data?.bboxes3d as LocalBBox3D[] | undefined) ?? []).map((bbox) => {
      const ov = storage.overrides[bbox.id];
      if (!ov) return bbox;
      return { ...bbox, coords: ov.coords, rotation: ov.rotation ?? bbox.rotation };
    }),
    ...storage.drafts.map(
      (d): LocalBBox3D => ({
        id: d.id,
        record_id: recordId,
        entity_id: d.entityId,
        view_id: viewId,
        coords: d.coordsLance,
        format: "xyzwhd",
        rotation: d.rotation ?? DEFAULT_3D_ROTATION,
        is_normalized: false,
        entity: d.entity,
      }),
    ),
  ]);
</script>

<div class="relative flex h-full w-full flex-col bg-card">
  <!-- Toolbar -->
  <div
    class="flex items-center gap-0.5 border-b border-border bg-muted/30 px-1.5 py-0.5"
    onpointerdown={(e) => e.stopPropagation()}
    role="toolbar"
    aria-label="Point cloud tools"
    tabindex="0"
  >
    <button
      type="button"
      onclick={() => (storage.mode = "navigate")}
      title="Navigate"
      class="rounded p-1 text-muted-foreground hover:bg-accent hover:text-accent-foreground {storage.mode === 'navigate' ? 'bg-accent text-accent-foreground' : ''}"
    >
      <MousePointer2 class="h-3.5 w-3.5" />
    </button>
    <button
      type="button"
      onclick={() => (storage.mode = storage.mode === "draw-bbox3d" ? "navigate" : "draw-bbox3d")}
      title="Draw 3D box"
      class="rounded p-1 text-muted-foreground hover:bg-accent hover:text-accent-foreground {storage.mode === 'draw-bbox3d' ? 'bg-accent text-accent-foreground' : ''}"
    >
      <Box class="h-3.5 w-3.5" />
    </button>
    <div class="mx-1 h-4 w-px bg-border"></div>
    <button
      type="button"
      onclick={() => (cameraMode = "orbit")}
      title="Orbit mode (Left drag to orbit · Right drag to pan · Scroll to zoom)"
      class="rounded p-1 text-muted-foreground hover:bg-accent hover:text-accent-foreground {cameraMode === 'orbit' ? 'bg-accent text-accent-foreground' : ''}"
    >
      <Globe class="h-3.5 w-3.5" />
    </button>
    <button
      type="button"
      onclick={() => (cameraMode = "first-person")}
      title="First person mode (Left drag to pan · Right drag to look around · Scroll to move forward/back)"
      class="rounded p-1 text-muted-foreground hover:bg-accent hover:text-accent-foreground {cameraMode === 'first-person' ? 'bg-accent text-accent-foreground' : ''}"
    >
      <Eye class="h-3.5 w-3.5" />
    </button>
    <div class="mx-1 h-4 w-px bg-border"></div>
    <button
      type="button"
      onclick={() => manager.flushSave()}
      disabled={manager.pendingCount === 0 || manager.saving}
      title="Save annotations"
      class="rounded p-1 text-muted-foreground hover:bg-accent hover:text-accent-foreground disabled:cursor-not-allowed disabled:opacity-40"
    >
      <Save class="h-3.5 w-3.5" />
    </button>
    {#if manager.pendingCount > 0}
      <span class="ml-1 text-[10px] text-muted-foreground">{manager.pendingCount} unsaved</span>
    {/if}
    {#if manager.saveError}
      <span class="ml-1 max-w-[200px] truncate text-[10px] text-destructive" title={manager.saveError}>Save failed</span>
    {/if}
  </div>

  <!-- 3D canvas area -->
  {#if error}
    <div class="flex flex-1 items-center justify-center">
      <div class="text-center text-muted-foreground">
        <div class="mb-1 text-sm">3D Viewer Error</div>
        <div class="text-xs">{error}</div>
      </div>
    </div>
  {:else if ready && CanvasComponent && SceneComponent}
    <div bind:this={canvasEl} class="relative flex-1" onpointerdown={(e) => e.stopPropagation()}>
      <div class="absolute inset-0">
        <CanvasComponent>
          <SceneComponent
            bind:this={sceneRef}
            pointCloudUrl={data?.pointCloudUrl as string | undefined}
            bboxes3d={allBboxes3d}
            drawMode={storage.mode === "draw-bbox3d"}
            {cameraMode}
            onReadyToConfirm={handleReadyToConfirm}
            onDrawCanceled={handleDrawCanceled}
            onLoadError={(msg) => (error = msg)}
            {gizmoVisibility}
          />
        </CanvasComponent>
      </div>

      <!-- Confirm overlay -->
      {#if confirmCoords}
        <div class="pointer-events-none absolute inset-x-0 bottom-4 flex justify-center">
          <div class="pointer-events-auto flex items-center gap-2 rounded-lg border border-border bg-background/95 px-3 py-2 text-sm shadow-lg backdrop-blur-sm">
            <span class="text-muted-foreground">Save this 3D box?</span>
            <button
              type="button"
              onclick={handleConfirmSave}
              class="rounded bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground hover:bg-primary/90"
            >
              Save
            </button>
            <button
              type="button"
              onclick={handleConfirmCancel}
              class="rounded border border-border px-2.5 py-1 text-xs hover:bg-accent"
            >
              Cancel
            </button>
            <div class="mx-1 h-4 w-px bg-border"></div>
            <button
              type="button"
              onclick={() => (gizmoVisibility = { ...gizmoVisibility, rings: !gizmoVisibility.rings })}
              title={gizmoVisibility.rings ? "Hide rotation rings" : "Show rotation rings"}
              class="rounded p-1 text-muted-foreground hover:bg-accent hover:text-accent-foreground {gizmoVisibility.rings ? 'bg-accent text-accent-foreground' : ''}"
            >
              <Orbit class="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onclick={() => (gizmoVisibility = { ...gizmoVisibility, resizeArrows: !gizmoVisibility.resizeArrows })}
              title={gizmoVisibility.resizeArrows ? "Hide resize arrows" : "Show resize arrows"}
              class="rounded p-1 text-muted-foreground hover:bg-accent hover:text-accent-foreground {gizmoVisibility.resizeArrows ? 'bg-accent text-accent-foreground' : ''}"
            >
              <Scaling class="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onclick={() => (gizmoVisibility = { ...gizmoVisibility, translateArrows: !gizmoVisibility.translateArrows })}
              title={gizmoVisibility.translateArrows ? "Hide translate arrows" : "Show translate arrows"}
              class="rounded p-1 text-muted-foreground hover:bg-accent hover:text-accent-foreground {gizmoVisibility.translateArrows ? 'bg-accent text-accent-foreground' : ''}"
            >
              <Move class="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      {/if}
    </div>
  {:else}
    <div class="flex flex-1 items-center justify-center">
      <div class="text-xs text-muted-foreground">Loading 3D viewer...</div>
    </div>
  {/if}
</div>
