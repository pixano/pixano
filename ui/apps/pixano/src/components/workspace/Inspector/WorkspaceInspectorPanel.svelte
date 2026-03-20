<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { BoundingBox, PencilSimple } from "phosphor-svelte";

  import SaveShapeForm from "../SaveShape/SaveShapeForm.svelte";
  import EntitiesInspector from "./EntitiesInspector.svelte";
  import SceneInspector from "./SceneInspector.svelte";
  import { newShape } from "$lib/stores/workspaceStores.svelte";
  import { Skeleton, Tabs } from "$lib/ui";

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
      <div class="shrink-0 border-b border-border/50 bg-card px-2.5 py-2">
        <Tabs.List
          class="grid grid-cols-2 rounded-xl border border-border/60 bg-muted/20 p-1 gap-1"
        >
          <Tabs.Trigger
            value="objects"
            class="inline-flex items-center justify-center gap-2 rounded-lg px-2.5 py-2 text-xs font-semibold text-muted-foreground transition-all duration-200 data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm data-[state=active]:ring-1 data-[state=active]:ring-border/60"
          >
            <BoundingBox class="h-4 w-4" />
            Entities
          </Tabs.Trigger>
          <Tabs.Trigger
            value="scene"
            class="inline-flex items-center justify-center gap-2 rounded-lg px-2.5 py-2 text-xs font-semibold text-muted-foreground transition-all duration-200 data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm data-[state=active]:ring-1 data-[state=active]:ring-border/60"
          >
            <PencilSimple class="h-4 w-4" />
            Scene
          </Tabs.Trigger>
        </Tabs.List>
      </div>

      <Tabs.Content
        value="objects"
        class="flex-1 min-h-0 overflow-y-auto scroll-smooth"
        id="card-object-container"
      >
        {#if isLoading}
          <div class="p-3 space-y-3 animate-in fade-in duration-300">
            <div class="rounded-xl border border-border/50 bg-card/80 p-3 space-y-3 shadow-sm">
              <div class="flex items-center justify-between gap-3">
                <Skeleton class="h-4 w-24" />
                <Skeleton class="h-4 w-12" />
              </div>
              <Skeleton class="h-8 w-full" />
            </div>

            <div class="space-y-2">
              {#each loadingObjectRows as rowIndex}
                <div
                  class="rounded-xl border border-border/50 bg-card/90 p-3 shadow-sm animate-in fade-in slide-in-from-bottom-1 duration-500"
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
      <Tabs.Content value="scene" class="flex-1 min-h-0 overflow-y-auto scroll-smooth">
        {#if currentTab === "scene"}
          {#if isLoading}
            <div class="p-4 flex flex-col gap-4 animate-in fade-in duration-300">
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
