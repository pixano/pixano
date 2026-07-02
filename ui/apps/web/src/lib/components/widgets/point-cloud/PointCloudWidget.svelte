<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Eye, Globe } from "lucide-svelte";
  import { getContext, onMount } from "svelte";
  import type { Component } from "svelte";

  // Type-only import (erased at runtime, so the dynamic import below still
  // code-splits) — gives the scene's exact prop types to the lazy holder.
  import type PointCloudSceneComponent from "./PointCloudScene.svelte";

  import { DEFAULT_TOOL_3D, TOOLS_3D } from "$lib/annotations/scene/registry3d.js";
  import type { PointCloudWidgetStorage } from "$lib/annotations/types.js";
  import type { WorkspaceManager } from "$lib/workspace/workspaceManager.svelte.js";

  import AnnotationToolbar from "../AnnotationToolbar.svelte";
  import { buildSeam } from "../sceneSeam.js";

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

  // The medium-agnostic seam: this view's window onto the shared collection
  // plus the mutation sink. PointCloudScene completes it into a Scene3DContext.
  // (Threlte redraws on reactive invalidation, so no imperative redraw hook.)
  const seam = buildSeam(manager, {
    widgetId: stableWidgetId,
    buildContext: { datasetId, recordId, viewId },
    storage,
  });

  let cameraMode = $state<"orbit" | "first-person">("orbit");

  let ready = $state(false);
  let error = $state<string | null>(null);
  let CanvasComponent = $state<Component | null>(null);
  let SceneComponent = $state<typeof PointCloudSceneComponent | null>(null);
  let canvasEl = $state<HTMLDivElement | null>(null);

  // Per-tool editing sessions (kind-owned confirm state + commit), created once.
  // The widget is a courier: it never reads a session's fields — it only routes
  // each session to the tool's scene overlay (via toolProps) and its DOM HUD.
  const sessions: Record<string, unknown> = {};
  const toolProps: Record<string, { session: unknown }> = {};
  for (const tool of TOOLS_3D) {
    if (tool.createSession) {
      const session = tool.createSession(seam);
      sessions[tool.id] = session;
      toolProps[tool.id] = { session };
    }
  }

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
</script>

<div class="relative flex h-full w-full flex-col bg-card">
  <!-- Toolbar -->
  <AnnotationToolbar
    tools={TOOLS_3D}
    activeToolId={storage.activeToolId}
    defaultToolId={DEFAULT_TOOL_3D}
    onSelectTool={(id) => (storage.activeToolId = id)}
    pendingCount={manager.pendingCount}
    saveDisabled={manager.pendingCount === 0 || manager.saving}
    saving={manager.saving}
    saveError={manager.saveError}
    onSave={() => manager.flushSave()}
    ariaLabel="Point cloud tools"
  >
    {#snippet controls()}
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
    {/snippet}
  </AnnotationToolbar>

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
            pointCloudUrl={data?.pointCloudUrl as string | undefined}
            {seam}
            activeToolId={storage.activeToolId}
            {cameraMode}
            onLoadError={(msg: string) => (error = msg)}
            {toolProps}
          />
        </CanvasComponent>
      </div>

      <!-- Active tool's DOM HUD (e.g. the bbox3d confirm panel), owned by the
           kind. The widget mounts it but names no kind. -->
      {#each TOOLS_3D as tool (tool.id)}
        <!-- A HUD only renders for the active tool that also provided a session
             (a `hud` without a `createSession` would otherwise crash — DEBT-6). -->
        {#if tool.hud && tool.id === storage.activeToolId && sessions[tool.id]}
          {@const Hud = tool.hud}
          <Hud session={sessions[tool.id]} />
        {/if}
      {/each}
    </div>
  {:else}
    <div class="flex flex-1 items-center justify-center">
      <div class="text-xs text-muted-foreground">Loading 3D viewer...</div>
    </div>
  {/if}
</div>
