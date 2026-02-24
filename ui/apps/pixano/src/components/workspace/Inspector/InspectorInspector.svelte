<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Skeleton, Tabs } from "$lib/ui";

  import { newShape } from "$lib/stores/workspaceStores.svelte";
  import SaveShapeForm from "../SaveShape/SaveShapeForm.svelte";
  import EntitiesInspector from "./EntitiesInspector.svelte";
  import SceneInspector from "./SceneInspector.svelte";

  interface Props {
    isLoading: boolean;
  }

  let { isLoading }: Props = $props();

  let currentTab: "scene" | "objects" = $state("objects");
  const loadingObjectRows = Array.from({ length: 7 }, (_, index) => index);
  const loadingTitleWidths = [48, 62, 53, 58, 44];
  const loadingSubtitleWidths = [28, 34, 26, 31];
</script>

<div class="h-full flex flex-col border-l border-border bg-card font-sans overflow-hidden">
  {#if newShape.value?.status === "saving"}
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
          <div class="p-3 space-y-3">
            <div class="rounded-xl border border-border/50 bg-muted/20 p-3 space-y-3">
              <div class="flex items-center justify-between gap-3">
                <Skeleton class="h-4 w-24" />
                <Skeleton class="h-4 w-12" />
              </div>
              <Skeleton class="h-8 w-full" />
            </div>

            <div class="space-y-2">
              {#each loadingObjectRows as rowIndex}
                <div
                  class="rounded-lg border border-border/50 bg-card p-3 animate-in fade-in slide-in-from-bottom-1 duration-500"
                  style={`animation-delay: ${rowIndex * 80}ms`}
                >
                  <div class="flex items-center gap-3">
                    <Skeleton class="h-8 w-8 rounded-full shrink-0" />
                    <div class="flex-1 space-y-2">
                      <Skeleton
                        class="h-3.5"
                        style={`width: ${loadingTitleWidths[rowIndex % loadingTitleWidths.length]}%`}
                      />
                      <Skeleton
                        class="h-3"
                        style={`width: ${loadingSubtitleWidths[rowIndex % loadingSubtitleWidths.length]}%`}
                      />
                    </div>
                    <Skeleton class="h-5 w-12 rounded-full shrink-0" />
                  </div>
                </div>
              {/each}
            </div>
          </div>
        {:else}
          <EntitiesInspector />
        {/if}
      </Tabs.Content>
      <Tabs.Content value="scene" class="flex-1 overflow-y-auto scroll-smooth">
        {#if currentTab === "scene"}
          {#if isLoading}
            <div class="p-4 flex flex-col gap-4">
              <Skeleton class="h-8 w-full" />
              <Skeleton class="h-8 w-full" />
              <Skeleton class="h-8 w-full" />
            </div>
          {:else}
            <SceneInspector />
          {/if}
        {/if}
      </Tabs.Content>
    </Tabs.Root>
  {/if}
</div>
