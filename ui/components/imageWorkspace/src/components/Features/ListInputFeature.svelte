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

  import { Combobox } from "@pixano/core/src";

  import type { ListFeature } from "../../lib/types/imageWorkspaceTypes";

  export let listFeature: Pick<ListFeature, "name" | "value" | "options">;
  export let isEditing: boolean;
  export let handleInputChange: (value: string, propertyName: string) => void;
</script>

{#if isEditing}
  <Combobox
    placeholder={`Select a ${listFeature.name}`}
    listItems={listFeature.options}
    saveValue={(value) => handleInputChange(value, listFeature.name)}
    value={listFeature.value}
  />
{:else if listFeature.value}
  <p class="first-letter:uppercase">
    {listFeature.value}
  </p>
{/if}
