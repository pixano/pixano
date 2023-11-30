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

  import { PlusCircle } from "lucide-svelte";

  import type { tools } from "@pixano/canvas2d";
  import { Button } from "@pixano/core/src/lib/components/ui/button";
  import { Input } from "@pixano/core/src/lib/components/ui/input";
  import { Checkbox } from "@pixano/core/src/lib/components/ui/checkbox";
  import IconButton from "@pixano/core/src/lib/components/molecules/TooltipIconButton.svelte";

  import { newShape } from "../lib/stores/stores";

  import { objectSetup } from "../lib/settings/objectSetting";

  let shape: tools.Shape;

  newShape.subscribe((value) => {
    if (value) shape = value;
  });

  let value = "";

  const addTextInput = () => {
    // objectSetup.update((prev) => {
    //   const newSetup = [...prev];
    //   newSetup.push({
    //     type: "text",
    //     label: "Label",
    //     multiple: true,
    //   });
    //   return newSetup;
    // });
  };
</script>

<p>{shape.status}</p>

<form class="flex flex-col gap-4 p-4">
  {#each objectSetup as obj}
    {#if obj.type === "checkbox"}
      <div class="flex gap-4">
        <Checkbox />
        <span>{obj.label}</span>
      </div>
    {/if}
    {#if obj.type === "text"}
      <div>
        <span>{obj.label}</span>
        {#if obj.multiple}
          <span
            ><IconButton
              ><PlusCircle class="w-8 h-8" strokeWidth={1} on:click={addTextInput} /></IconButton
            ></span
          >
        {/if}
        <Input bind:value />
      </div>
    {/if}
    {#if obj.type === "number"}
      <div>
        <span>{obj.label}</span>
        <Input type="number" />
      </div>
    {/if}
  {/each}
  <div>
    <span>Label</span>
    <Input />
  </div>
  <Input type="number" />
  <Checkbox />
  <div class="flex gap-4">
    <Button on:click={() => newShape.set(null)}>cancel</Button>
    <Button on:click={() => newShape.set(null)}>confirm</Button>
  </div>
</form>
