<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Combobox } from "@pixano/core/src";

  import type { ListFeature } from "../../lib/types/datasetItemWorkspaceTypes";

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
