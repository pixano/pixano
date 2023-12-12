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

  import { Checkbox } from "@pixano/core/src/lib/components/ui/checkbox";
  import type { ObjectFeature, ItemObject } from "@pixano/core";

  import { objectSetup } from "../../lib/settings/objectSetting";

  import FeatureTextInput from "./ActionsTabFeatureInput.svelte";
  import { itemObjects } from "../../lib/stores/stores";

  export let itemObject: ItemObject;
  export let isEditing: boolean;

  $: features = objectSetup
    .map((property) => {
      const value = itemObject.features[property.name]?.value;
      if (typeof value !== "string" && typeof value !== "number" && typeof value !== "boolean") {
        return;
      }
      return {
        ...property,
        label: property.label,
        name: property.name,
        value: typeof value === "string" ? [value] : value,
      };
    })
    .filter(Boolean) as ObjectFeature[];

  const saveInputChange = (value: string, propertyName: string, itemObjectId: string) => {
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
        return object;
      }),
    );
  };
</script>

{#each features as feature}
  {#if !feature.value}
    <div>erreur. Merci de vous adresser aux administrateurs</div>
  {/if}
  <p class="font-medium pb-1">{feature.label}</p>
  {#if feature.type === "checkbox"}
    <Checkbox checked={feature.value} disabled />
  {/if}
  {#if feature.type === "text"}
    <FeatureTextInput
      saveInputChange={(value, name) => saveInputChange(value, name, itemObject.id)}
      textFeature={feature}
      {isEditing}
    />
  {/if}
  {#if feature.type === "number"}
    <span class="rounded-full bg-primary-light h-5 w-5 flex justify-center items-center">
      {feature.value}
    </span>
  {/if}
{/each}
