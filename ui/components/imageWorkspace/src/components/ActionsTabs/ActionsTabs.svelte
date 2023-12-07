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

  import * as Tabs from "@pixano/core/src/lib/components/ui/tabs";
  import type { Shape } from "@pixano/core";

  import SceneTabContent from "./SceneTabContent.svelte";
  import ObjectTabContent from "./ObjectTabContent.svelte";
  import SaveShapeForm from "../SaveShape/SaveShapeForm.svelte";
  import { newShape } from "../../lib/stores/stores";

  let shape: Shape | null;

  newShape.subscribe((value) => {
    shape = value;
  });
</script>

<div class="h-full max-h-screen shadow-md w-10 bg-popover flex-[2_0_auto]">
  {#if shape}
    <SaveShapeForm />
  {:else}
    <Tabs.Root value="objects">
      <Tabs.List class="h-[48px]">
        <Tabs.Trigger value="scene">Scene</Tabs.Trigger>
        <Tabs.Trigger value="objects">Objets</Tabs.Trigger>
      </Tabs.List>
      <Tabs.Content value="scene" class="bg-red max-h-[calc(100vh-140px)] overflow-y-auto">
        <SceneTabContent />
      </Tabs.Content>
      <Tabs.Content value="objects" class="bg-red max-h-[calc(100vh-140px)] overflow-y-auto"
        ><ObjectTabContent /></Tabs.Content
      >
    </Tabs.Root>
  {/if}
</div>
