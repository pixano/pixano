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

  import type { TextFeature, IntFeature, FloatFeature } from "../../lib/types/imageWorkspaceTypes";

  export let textFeature: Pick<IntFeature | FloatFeature | TextFeature, "name" | "value">;
  export let isEditing: boolean;
  export let saveInputChange: (value: string | number, propertyName: string) => void;
  export let inputType: "str" | "int" | "float" = "str";

  let isSaved = false;

  const onTextInputChange = (value: string, propertyName: string) => {
    const formattedValue = inputType === "str" ? value : Number(value);
    saveInputChange(formattedValue, propertyName);
    isSaved = true;
  };
</script>

<div class="flex justify-start items-center gap-4">
  {#if isEditing}
    {#if inputType === "str"}
      <Input
        value={textFeature.value}
        on:change={(e) => onTextInputChange(e.currentTarget.value, textFeature.name)}
        on:input={() => (isSaved = false)}
        type="text"
      />
    {:else if inputType === "int"}
      <Input
        value={textFeature.value}
        on:change={(e) => onTextInputChange(e.currentTarget.value, textFeature.name)}
        on:input={() => (isSaved = false)}
        type="number"
        step="1"
      />
    {:else if inputType === "float"}
      <Input
        value={textFeature.value}
        on:change={(e) => onTextInputChange(e.currentTarget.value, textFeature.name)}
        on:input={() => (isSaved = false)}
        type="number"
        step="any"
      />
    {/if}
    {#if isSaved}
      <span class="text-green-700">
        <CheckCheckIcon />
      </span>
    {/if}
  {:else if textFeature.value || textFeature.value === 0}
    <p
      class="font-light rounded-xl bg-primary-light first-letter:uppercase flex justify-center items-center h-6 py-1 px-3"
    >
      {textFeature.value}
    </p>
  {/if}
</div>
