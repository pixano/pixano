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

  import { CheckCheckIcon } from "lucide-svelte";

  import { Input } from "@pixano/core/src";

  import type { TextFeature, NumberFeature } from "../../lib/types/imageWorkspaceTypes";

  export let textFeature: Pick<NumberFeature | TextFeature, "name" | "value">;
  export let isEditing: boolean;
  export let saveInputChange: (value: string | number, propertyName: string) => void;
  export let inputType: NumberFeature["type"] | TextFeature["type"] = "str";

  let isSaved = false;

  const onTextInputChange = (value: string, propertyName: string) => {
    let formattedValue: string | number = value;
    if (inputType === "int") {
      formattedValue = Math.round(Number(value));
    } else if (inputType === "float") {
      formattedValue = Number(value);
    }
    saveInputChange(formattedValue, propertyName);
    isSaved = true;
  };
</script>

<div class="flex justify-start items-center gap-4">
  {#if isEditing}
    <Input
      value={textFeature.value}
      on:change={(e) => onTextInputChange(e.currentTarget.value, textFeature.name)}
      on:input={() => (isSaved = false)}
      type={inputType === "str" ? "text" : "number"}
      step={inputType === "int" ? "1" : "any"}
      on:keyup={(e) => e.stopPropagation()}
    />
    {#if isSaved}
      <span class="text-green-700">
        <CheckCheckIcon />
      </span>
    {/if}
  {:else if textFeature.value || textFeature.value === 0}
    <p class="first-letter:uppercase">
      {textFeature.value}
    </p>
  {/if}
</div>
