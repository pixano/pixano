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

  import { utils } from "@pixano/core";

  import ObjectTabFlatItem from "./ObjectTabFlatItem.svelte";
  import ActionsTabsSearchInput from "./ObjectTabModelContent.svelte";
  import { itemObjects, colorRange } from "../../lib/stores/stores";
  import { GROUND_TRUTH, MODEL_RUN } from "../../lib/constants";
  import { sortObjectsByModel } from "../../lib/api/objectsApi";
  import type { ObjectsSortedByModelType } from "../../lib/types/imageWorkspaceTypes";

  let allItemsSortedByModel: ObjectsSortedByModelType = {
    [GROUND_TRUTH]: [],
    [MODEL_RUN]: [],
  };

  itemObjects.subscribe((value) => {
    allItemsSortedByModel = sortObjectsByModel(value);
  });

  let colorRangeValue: string[] = [];
  colorRange.subscribe((value) => (colorRangeValue = value));
  let colorScale = utils.ordinalColorScale(colorRangeValue);
</script>

<div class="p-2">
  <div>
    <ActionsTabsSearchInput sectionTitle={"Ground truth"} modelName={GROUND_TRUTH}>
      {#each allItemsSortedByModel[GROUND_TRUTH] as itemObject}
        <ObjectTabFlatItem bind:itemObject {colorScale} />
      {/each}
    </ActionsTabsSearchInput>
  </div>
  <ActionsTabsSearchInput sectionTitle={"Model run"} modelName={MODEL_RUN}>
    {#each allItemsSortedByModel[MODEL_RUN] as model}
      <ActionsTabsSearchInput sectionTitle={model.modelName} modelName={model.modelName}>
        {#each model.objects as itemObject}
          <ObjectTabFlatItem bind:itemObject {colorScale} />
        {/each}
      </ActionsTabsSearchInput>
    {/each}
  </ActionsTabsSearchInput>
</div>
