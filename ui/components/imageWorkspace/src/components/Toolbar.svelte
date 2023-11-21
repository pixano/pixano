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
  import { MousePointer, Square, Share2, BrushIcon } from "lucide-svelte";
  import { Button } from "@pixano/core/src/lib/components/ui/button";
  import * as Tooltip from "@pixano/core/src/lib/components/ui/tooltip";
</script>

<div class="h-full shadow-md w-10 bg-popover">
  <div class="border-b border-gray-400 pb-4 flex items-center flex-col gap-4 bg-popover">
    <Tooltip.Root>
      <Tooltip.Trigger>
        <Button size="icon" class="bg-transparent text-gray-800 hover:bg-primary-light">
          <MousePointer />
        </Button></Tooltip.Trigger
      >
      <Tooltip.Content>
        <p>TODO</p>
      </Tooltip.Content>
    </Tooltip.Root>
    <Tooltip.Root>
      <Tooltip.Trigger
        ><Button size="icon" class="bg-transparent text-gray-800 hover:bg-primary-light"
          ><Square /></Button
        ></Tooltip.Trigger
      >
      <Tooltip.Content>
        <p>TODO</p>
      </Tooltip.Content>
    </Tooltip.Root>
    <Tooltip.Root>
      <Tooltip.Trigger
        ><Button size="icon" class="bg-transparent text-gray-800 hover:bg-primary-light"
          ><Share2 /></Button
        ></Tooltip.Trigger
      >
      <Tooltip.Content>
        <p>TODO</p>
      </Tooltip.Content>
    </Tooltip.Root>
    <Tooltip.Root>
      <Tooltip.Trigger
        ><Button size="icon" class="bg-transparent text-gray-800 hover:bg-primary-light"
          ><BrushIcon /></Button
        ></Tooltip.Trigger
      >
      <Tooltip.Content>
        <p>TODO</p>
      </Tooltip.Content>
    </Tooltip.Root>
  </div>
  <div class="flex items-center flex-col gap-4 mt-4">
    <Tooltip.Root>
      <Tooltip.Trigger
        ><Button size="icon" class="bg-transparent text-gray-800 hover:bg-primary-light"
          ><BrushIcon /></Button
        ></Tooltip.Trigger
      >
      <Tooltip.Content>
        <p>TODO</p>
      </Tooltip.Content>
    </Tooltip.Root>
    <Tooltip.Root>
      <Tooltip.Trigger
        ><Button size="icon" class="bg-transparent text-gray-800 hover:bg-primary-light"
          ><Square /></Button
        ></Tooltip.Trigger
      >
      <Tooltip.Content>
        <p>TODO</p>
      </Tooltip.Content>
    </Tooltip.Root>
  </div>
</div>
