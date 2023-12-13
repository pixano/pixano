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

  import Combobox from "@pixano/core/src/lib/components/ui/combobox/combobox.svelte";

  import type { ListFeature } from "../../lib/types/imageWorkspaceTypes";
  import { objectSetup } from "../../lib/settings/objectValidationSchemas";
  import type { ListInput } from "../../lib/types/imageWorkspaceTypes";

  export let listFeature: Pick<ListFeature, "name" | "value">;
  export let isEditing: boolean;
  export let handleInputChange: (value: string, propertyName: string) => void;

  let currentObject = objectSetup.find((o) => o.name === listFeature.name) as ListInput;
</script>

{#if isEditing}
  <Combobox
    placeholder={`Select a ${currentObject.name}`}
    listItems={currentObject.options}
    saveValue={(value) => handleInputChange(value, currentObject.name)}
    value={listFeature.value}
  />
{:else if listFeature.value}
  <p
    class="font-light rounded-xl bg-primary-light first-letter:uppercase flex justify-center items-center h-6 py-1 px-3 w-min"
  >
    {listFeature.value}
  </p>
{/if}
