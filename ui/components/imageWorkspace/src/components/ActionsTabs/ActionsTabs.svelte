<script lang="ts">
  /**
   * @copyright CEA
   * @author CEA
   * @license CECILL
   *
   * This software is a collaborative computer program whose purpose is to
   * generate and explore labeled data for computer vision applications.
   * This software is governed by the CeCILL-C license under French law and
   * abiding by the rules of distribution of free software. You can use,
   * modify and/ or redistribute the software under the terms of the CeCILL-C
   * license as circulated by CEA, CNRS and INRIA at the following URL
   *
   * http://www.cecill.info
   */

  import type { Shape } from "@pixano/core";
  import { cn, Tabs, Skeleton } from "@pixano/core/src";

  import SceneTabContent from "./SceneTabContent.svelte";
  import ObjectTabContent from "./ObjectTabContent.svelte";
  import SaveShapeForm from "../SaveShape/SaveShapeForm.svelte";
  import { canSave, newShape } from "../../lib/stores/imageWorkspaceStores";

  export let isLoading: boolean;
  let shape: Shape;
  let currentTab: "scene" | "objects" = "scene";
  let isButtonEnabled = false;

  canSave.subscribe((value) => {
    isButtonEnabled = value;
  });

  newShape.subscribe((value) => {
    shape = value;
  });
</script>

<div class="h-full max-h-screen shadow-md bg-popover">
  {#if shape?.status === "inProgress"}
    <SaveShapeForm />
  {:else}
    <Tabs.Root bind:value={currentTab} class="h-full">
      <Tabs.List class="h-[48px]">
        <Tabs.Trigger value="scene">Scene</Tabs.Trigger>
        <Tabs.Trigger value="objects">Objets</Tabs.Trigger>
      </Tabs.List>
      <div class="h-[calc(100%-48px)] flex flex-col justify-between">
        <Tabs.Content value="scene" class="bg-red max-h-[calc(100vh-200px)] overflow-y-auto">
          {#if isLoading}
            <div class="p-4 flex flex-col gap-4">
              <Skeleton class="h-8 w-full" />
              <Skeleton class="h-8 w-full" />
              <Skeleton class="h-8 w-full" />
            </div>
          {:else}
            <SceneTabContent />
          {/if}
        </Tabs.Content>
        <Tabs.Content value="objects" class="bg-red max-h-[calc(100vh-200px)] overflow-y-auto">
          {#if isLoading}
            <div class="p-4 flex flex-col gap-4">
              <Skeleton class="h-8 w-full" />
              <Skeleton class="h-8 w-full" />
              <Skeleton class="h-8 w-full" />
            </div>
          {:else}
            <ObjectTabContent />
          {/if}
        </Tabs.Content>
        <button
          disabled={!isButtonEnabled}
          class={cn(
            "h-[48px] w-full border-t border-t-primary-light hover:bg-primary-light hover:cursor-pointer",
            {
              "bg-slate-50 hover:bg-slate-50 pointer-events-none cursor-not-allowed text-slate-500":
                !isButtonEnabled,
            },
          )}
          on:click>SAVE CHANGES</button
        >
      </div>
    </Tabs.Root>
  {/if}
</div>
