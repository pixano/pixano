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

<div
  class="h-[calc(100vh-80px)] flex flex-col overflow-y-auto shadow-sm border-l border-slate-200 bg-slate-100 font-Montserrat"
>
  {#if $newShape?.status === "saving"}
    <SaveShapeForm bind:currentTab />
  {:else}
    <Tabs.Root bind:value={currentTab} class="flex flex-col">
      <Tabs.List class="flex h-12">
        <Tabs.Trigger value="objects">Objects</Tabs.Trigger>
        <Tabs.Trigger value="scene">Scene</Tabs.Trigger>
      </Tabs.List>
      <Tabs.Content value="objects">
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
      <Tabs.Content value="scene">
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
