<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Eye, Globe, Move, Orbit, Save, Scaling } from "lucide-svelte";
  import { getContext, onMount } from "svelte";
  import type { Component } from "svelte";

  import type {
    BBox3DGeometry,
    LocalBBox3DAnnotation,
  } from "$lib/annotations/annotationCollection.svelte.js";
  import { DEFAULT_3D_ROTATION, generateShortId } from "$lib/annotations/buildPayloads.js";
  import {
    BBOX3D_RESOURCE,
    bbox3dPayloadBuilder,
  } from "$lib/annotations/kinds/3d/bbox3d/bbox3dPayloadBuilder.js";
  import { commitDraftWithEntity, reassignEntity } from "$lib/annotations/payloadBuilders.js";
  import { DEFAULT_TOOL_3D, TOOLS_3D } from "$lib/annotations/tools/registry3d.js";
  import type { PendingEntityChoice, PointCloudWidgetStorage } from "$lib/annotations/types.js";
  import type { LocalBBox3D } from "$lib/api/annotations.js";
  import type { WorkspaceManager } from "$lib/workspace/workspaceManager.svelte.js";

  import type { GizmoVisibility } from "$lib/annotations/kinds/3d/bbox3d/bbox3dTypes.js";

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

  let ready = $state(false);
  let error = $state<string | null>(null);
  let CanvasComponent = $state<Component | null>(null);
  let SceneComponent = $state<Component | null>(null);
  let canvasEl = $state<HTMLDivElement | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let sceneRef = $state<any>(null);

  let confirmCoords = $state<[number, number, number, number, number, number] | null>(null);
  let confirmRotation = $state<number[] | undefined>(undefined);
  let gizmoVisibility = $state<GizmoVisibility>({
    rings: true,
    resizeArrows: true,
    translateArrows: true,
  });

  const GIZMO_TOGGLES: { key: keyof GizmoVisibility; icon: typeof Orbit; label: string }[] = [
    { key: "rings", icon: Orbit, label: "rotation rings" },
    { key: "resizeArrows", icon: Scaling, label: "resize arrows" },
    { key: "translateArrows", icon: Move, label: "translate arrows" },
  ];

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
    const tool = TOOLS_3D.find((t) => t.id === storage.activeToolId);
    canvasEl.style.cursor = tool?.cursor ?? "default";
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
    const annotation = manager.annotations.find(boxId);
    if (!annotation) return;

    const geometry: BBox3DGeometry = { coords, format: "xyzwhd", rotation };
    manager.annotations.setGeometry(boxId, geometry);

    if (annotation.persisted) {
      manager.upsertUpdateMutation({
        op: "update",
        resource: BBOX3D_RESOURCE,
        id: boxId,
        body: bbox3dPayloadBuilder.buildUpdate({ datasetId, recordId, viewId }, annotation as LocalBBox3DAnnotation),
        widgetId: stableWidgetId,
        localAnnotationId: boxId,
      });
    } else {
      manager.patchPendingCreateMutation(boxId, BBOX3D_RESOURCE, {
        coords: Array.from(coords),
        rotation: rotation ?? DEFAULT_3D_ROTATION,
      });
    }
  }

  function handleNewBoxSave(
    coords: [number, number, number, number, number, number],
    rotation: number[] | undefined,
  ): void {
    // Show the box right away as an unsaved draft; its entity (and the create
    // mutations) are assigned once the user confirms in the Inspector form.
    const localId = generateShortId();
    const draft: LocalBBox3DAnnotation = {
      id: localId,
      entityId: "",
      kind: "bbox3d",
      viewId,
      geometry: { coords, format: "xyzwhd", rotation },
      persisted: false,
    };
    manager.annotations.add(draft);

    manager.beginPendingAnnotation({
      label: "3D box",
      onConfirm: (choice: PendingEntityChoice) =>
        commitDraftWithEntity(draft, choice, {
          collection: manager.annotations,
          mutations: { queue: (m) => manager.queueMutation(m) },
          buildContext: { datasetId, recordId, viewId },
          widgetId: stableWidgetId,
          findEntity: (id) => manager.entities.find((e) => e.id === id),
        }),
      onCancel: () => manager.annotations.remove(localId),
    });
  }

  function handleConfirmCancel(): void {
    confirmCoords = null;
    confirmEditingId = null;
    sceneRef?.reset();
  }

  function handleConfirmDelete(): void {
    if (!confirmEditingId) return;
    const annotation = manager.annotations.find(confirmEditingId);
    if (annotation) manager.deleteAnnotation(annotation, stableWidgetId);
    confirmCoords = null;
    confirmEditingId = null;
    sceneRef?.reset();
  }

  function handleChangeEntity(): void {
    if (!confirmEditingId) return;
    const annotation = manager.annotations.find(confirmEditingId);
    if (!annotation) return;

    // Reuse the entity picker (Inspector form); on confirm, reassign the box to
    // the chosen entity — the backend prunes the previous one if it's orphaned.
    manager.beginPendingAnnotation({
      label: "3D box entity",
      onConfirm: (choice: PendingEntityChoice) =>
        reassignEntity(annotation, choice, {
          collection: manager.annotations,
          mutations: {
            queue: (m) => manager.queueMutation(m),
            upsertUpdate: (m) => manager.upsertUpdateMutation(m),
          },
          buildContext: { datasetId, recordId, viewId },
          widgetId: stableWidgetId,
          findEntity: (id) => manager.entities.find((e) => e.id === id),
        }),
      onCancel: () => {},
    });

    confirmCoords = null;
    confirmEditingId = null;
    sceneRef?.reset();
  }

  const allBboxes3d = $derived<LocalBBox3D[]>(
    manager.annotations
      .byKind("bbox3d")
      // Entity-driven visibility: hide persisted boxes whose entity is filtered
      // out; drafts (still being created) always show. Same shared filter the
      // 2D renderer applies, via the record-scoped session state.
      .filter((a) => !a.persisted || manager.isEntityVisible(a.entityId))
      .map(
        (a): LocalBBox3D => ({
        id: a.id,
        record_id: recordId,
        entity_id: a.entityId,
        view_id: viewId,
        coords: a.geometry.coords,
        format: a.geometry.format,
        rotation: a.geometry.rotation ?? DEFAULT_3D_ROTATION,
        is_normalized: false,
        entity: a.entity,
      }),
    ),
  );
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
    {#each TOOLS_3D as tool (tool.id)}
      <button
        type="button"
        onclick={() => (storage.activeToolId = storage.activeToolId === tool.id ? DEFAULT_TOOL_3D : tool.id)}
        title={tool.label}
        class="rounded p-1 text-muted-foreground hover:bg-accent hover:text-accent-foreground {storage.activeToolId === tool.id ? 'bg-accent text-accent-foreground' : ''}"
      >
        <tool.icon class="h-3.5 w-3.5" />
      </button>
    {/each}
    <div class="mx-1 h-4 w-px bg-border"></div>
    <button
      type="button"
      onclick={() => (cameraMode = "orbit")}
      title="Orbit mode (Left drag to orbit · Right drag to pan · Scroll to zoom)"
      class="rounded p-1 text-muted-foreground hover:bg-accent hover:text-accent-foreground {cameraMode ===
      'orbit'
        ? 'bg-accent text-accent-foreground'
        : ''}"
    >
      <Globe class="h-3.5 w-3.5" />
    </button>
    <button
      type="button"
      onclick={() => (cameraMode = "first-person")}
      title="First person mode (Left drag to pan · Right drag to look around · Scroll to move forward/back)"
      class="rounded p-1 text-muted-foreground hover:bg-accent hover:text-accent-foreground {cameraMode ===
      'first-person'
        ? 'bg-accent text-accent-foreground'
        : ''}"
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
      <span
        class="ml-1 max-w-[200px] truncate text-[10px] text-destructive"
        title={manager.saveError}
      >
        Save failed
      </span>
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
            activeToolId={storage.activeToolId}
            {cameraMode}
            onReadyToConfirm={handleReadyToConfirm}
            onDrawCanceled={handleDrawCanceled}
            onLoadError={(msg: string) => (error = msg)}
            {gizmoVisibility}
          />
        </CanvasComponent>
      </div>

      <!-- Confirm overlay -->
      {#if confirmCoords}
        <div class="pointer-events-none absolute inset-x-0 bottom-4 flex justify-center">
          <div
            class="pointer-events-auto flex items-center gap-2 rounded-lg border border-border bg-background/95 px-3 py-2 text-sm shadow-lg backdrop-blur-sm"
          >
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
            {#if confirmEditingId && manager.annotations.find(confirmEditingId)?.persisted}
              <button
                type="button"
                onclick={handleChangeEntity}
                title="Attach this 3D box to a different entity"
                class="rounded border border-border px-2.5 py-1 text-xs hover:bg-accent"
              >
                Change entity
              </button>
            {/if}
            {#if confirmEditingId}
              <button
                type="button"
                onclick={handleConfirmDelete}
                title="Delete this 3D box"
                class="rounded border border-destructive/40 px-2.5 py-1 text-xs text-destructive hover:bg-destructive hover:text-destructive-foreground"
              >
                Delete
              </button>
            {/if}
            <div class="mx-1 h-4 w-px bg-border"></div>
            {#each GIZMO_TOGGLES as toggle (toggle.key)}
              <button
                type="button"
                onclick={() =>
                  (gizmoVisibility = {
                    ...gizmoVisibility,
                    [toggle.key]: !gizmoVisibility[toggle.key],
                  })}
                title={gizmoVisibility[toggle.key]
                  ? `Hide ${toggle.label}`
                  : `Show ${toggle.label}`}
                class="rounded p-1 text-muted-foreground hover:bg-accent hover:text-accent-foreground {gizmoVisibility[
                  toggle.key
                ]
                  ? 'bg-accent text-accent-foreground'
                  : ''}"
              >
                <toggle.icon class="h-3.5 w-3.5" />
              </button>
            {/each}
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
