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

  import { Input } from "@pixano/core/src/lib/components/ui/input";
  import IconButton from "@pixano/core/src/lib/components/molecules/TooltipIconButton.svelte";

  import type { ObjectTextInput } from "../../lib/types/objects";

  export let textProperty: ObjectTextInput;
  export let handleTextInputChange: (values: string[], label: string) => void;

  let values: string[] = [""];

  const addTextInput = () => {
    values = [...values, ""];
  };

  const handleInputChange = (index: number, newValue: string) => {
    values = values.map((oldValue, j) => (index === j ? newValue : oldValue));
    handleTextInputChange(values, textProperty.label);
  };
</script>

<div>
  <span
    >{textProperty.label}
    {#if textProperty.required}
      *
    {/if}
  </span>
  <div class="flex flex-col gap-2">
    {#each values as value, i}
      <div class="flex">
        <Input {value} on:change={(e) => handleInputChange(i, e.currentTarget.value)} />
        {#if textProperty.multiple}
          <span
            ><IconButton on:click={addTextInput}
              ><PlusCircle class="w-8 h-8" strokeWidth={1} /></IconButton
            ></span
          >
        {/if}
      </div>
    {/each}
  </div>
</div>
