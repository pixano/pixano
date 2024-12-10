<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import type { Shape } from "@pixano/core";
  import { cn, Tabs, Skeleton } from "@pixano/core/src";

  import SceneInspector from "./SceneInspector.svelte";
  import ObjectsInspector from "./ObjectsInspector.svelte";
  import SaveShapeForm from "../SaveShape/SaveShapeForm.svelte";
  import { canSave, newShape } from "../../lib/stores/datasetItemWorkspaceStores";

  export let isLoading: boolean;

  let shape: Shape;
  let currentTab: "scene" | "objects" = "objects";
  let isButtonEnabled = false;

  canSave.subscribe((value) => {
    isButtonEnabled = value;
  });

  newShape.subscribe((value) => {
    shape = value;
  });
</script>

<div class="h-full max-h-screen shadow-sm border-l border-slate-200 bg-slate-100 font-Montserrat">
  {#if shape?.status === "saving"}
    <SaveShapeForm bind:currentTab />
  {:else}
    <Tabs.Root bind:value={currentTab} class="h-full">
      <Tabs.List class="h-[48px]">
        <Tabs.Trigger value="objects" class="w-1/2">Objects</Tabs.Trigger>
        <Tabs.Trigger value="scene" class="w-1/2 ">Scene</Tabs.Trigger>
      </Tabs.List>
      <div class="h-[calc(100%-48px)] flex flex-col justify-between">
        <Tabs.Content value="objects" class="h-full overflow-y-auto">
          {#if isLoading}
            <div class="p-4 flex flex-col gap-4">
              <Skeleton class="h-8 w-full" />
              <Skeleton class="h-8 w-full" />
              <Skeleton class="h-8 w-full" />
            </div>
          {:else}
            <ObjectsInspector />
          {/if}
        </Tabs.Content>
        <Tabs.Content value="scene" class="max-h-[calc(100vh-200px)] overflow-y-auto">
          {#if isLoading}
            <div class="p-4 flex flex-col gap-4">
              <Skeleton class="h-8 w-full" />
              <Skeleton class="h-8 w-full" />
              <Skeleton class="h-8 w-full" />
            </div>
          {:else}
            <SceneInspector />
          {/if}
        </Tabs.Content>
        <button
          disabled={!isButtonEnabled}
          class={cn(
            "h-12 w-full border-t border-t-primary-light hover:bg-primary-light hover:cursor-pointer bg-slate-50 z-50",
            {
              "bg-slate-100 hover:bg-slate-100 pointer-events-none cursor-not-allowed text-slate-500":
                !isButtonEnabled,
            },
          )}
          on:click>SAVE CHANGES</button
        >
      </div>
    </Tabs.Root>
  {/if}
</div>
