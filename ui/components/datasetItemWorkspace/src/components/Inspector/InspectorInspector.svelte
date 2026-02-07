<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Skeleton, Tabs } from "@pixano/core";

  import { newShape } from "../../lib/stores/datasetItemWorkspaceStores";
  import SaveShapeForm from "../SaveShape/SaveShapeForm.svelte";
  import ObjectsInspector from "./ObjectsInspector.svelte";
  import SceneInspector from "./SceneInspector.svelte";

  export let isLoading: boolean;

  let currentTab: "scene" | "objects" = "objects";
</script>

<div class="h-full flex flex-col border-l border-border bg-card font-DM Sans overflow-hidden">
  {#if $newShape?.status === "saving"}
    <SaveShapeForm bind:currentTab />
  {:else}
    <Tabs.Root bind:value={currentTab} class="flex flex-col h-full">
      <Tabs.List class="flex h-12 bg-muted/20 border-b border-border/50 px-1.5 gap-1">
        <Tabs.Trigger
          value="objects"
          class="data-[state=active]:bg-background data-[state=active]:shadow-sm rounded-md transition-all duration-200"
        >
          Objects
        </Tabs.Trigger>
        <Tabs.Trigger
          value="scene"
          class="data-[state=active]:bg-background data-[state=active]:shadow-sm rounded-md transition-all duration-200"
        >
          Scene
        </Tabs.Trigger>
      </Tabs.List>
      <Tabs.Content
        value="objects"
        class="flex-1 overflow-y-auto scroll-smooth"
        id="card-object-container"
      >
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
      <Tabs.Content value="scene" class="flex-1 overflow-y-auto scroll-smooth">
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
