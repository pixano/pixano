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

  import { Input } from "@pixano/core/src/lib/components/ui/input";
  import type { ObjectFeature, ItemObject } from "@pixano/core";

  import { itemObjects } from "../../lib/stores/stores";

  export let itemObjectId: ItemObject["id"];
  export let textFeature: ObjectFeature & { type: "text" };
  export let isEditing: boolean;

  let isSaved = false;

  const onTextInputChange = (value: string, propertyName: string) => {
    itemObjects.update((oldObjects) =>
      oldObjects.map((object) => {
        if (object.id === itemObjectId) {
          object.features = {
            ...object.features,
            [propertyName]: {
              ...object.features[propertyName],
              value,
            },
          };
        }
        isSaved = true;
        return object;
      }),
    );
  };
</script>

<div class="flex justify-start items-center gap-4">
  {#each textFeature.value as value}
    {#if isEditing}
      <Input
        {value}
        on:change={(e) => onTextInputChange(e.currentTarget.value, textFeature.name)}
        on:input={() => (isSaved = false)}
      />
      {#if isSaved}
        <span class="text-green-700">
          <CheckCheckIcon />
        </span>
      {/if}
    {:else}
      <p
        class=" font-light rounded-xl bg-primary-light first-letter:uppercase flex justify-center items-center h-6 py-1 px-3"
      >
        {value}
      </p>
    {/if}
  {/each}
</div>
