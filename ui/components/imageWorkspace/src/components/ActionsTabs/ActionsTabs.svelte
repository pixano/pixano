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

  import SceneTabContent from "./SceneTabContent.svelte";
  import ObjectTabContent from "./ObjectTabContent.svelte";
  import type { ObjectContent } from "../../lib/types/objects";

  export let allObjects: ObjectContent[];
</script>

<div class="h-full shadow-md w-10 bg-popover flex-[2_0_auto]">
  <Tabs.Root value="objects">
    <Tabs.List>
      <Tabs.Trigger value="scene">Scene</Tabs.Trigger>
      <Tabs.Trigger value="objects">Objets</Tabs.Trigger>
    </Tabs.List>
    <Tabs.Content value="scene">
      <SceneTabContent />
    </Tabs.Content>
    <Tabs.Content value="objects"><ObjectTabContent bind:allObjects /></Tabs.Content>
  </Tabs.Root>
</div>
