<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Skeleton, Tabs } from "@pixano/core/src";

  import { newShape } from "../../lib/stores/datasetItemWorkspaceStores";
  import SaveShapeForm from "../SaveShape/SaveShapeForm.svelte";
  import ObjectsInspector from "./ObjectsInspector.svelte";
  import SceneInspector from "./SceneInspector.svelte";

  export let isLoading: boolean;

  let currentTab: "scene" | "objects" = "objects";
</script>

<div class="h-full max-h-screen shadow-sm border-l border-slate-200 bg-slate-100 font-Montserrat">
  {#if $newShape?.status === "saving"}
    <SaveShapeForm bind:currentTab />
  {:else}
    <Tabs.Root bind:value={currentTab} class="h-full">
      <Tabs.List class="h-[48px]">
        <Tabs.Trigger value="objects" class="w-1/2">Objects</Tabs.Trigger>
        <Tabs.Trigger value="scene" class="w-1/2 ">Scene</Tabs.Trigger>
      </Tabs.List>
      <Tabs.Content value="objects" class="h-[calc(100%-48px)] overflow-y-auto">
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
    </Tabs.Root>
  {/if}
</div>
