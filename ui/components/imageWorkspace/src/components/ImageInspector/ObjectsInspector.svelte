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

  import ObjectItem from "./ObjectItem.svelte";
  import ObjectsModelSection from "./ObjectsModelSection.svelte";
  import { itemObjects } from "../../lib/stores/imageWorkspaceStores";
  import { GROUND_TRUTH, MODEL_RUN, PRE_ANNOTATION } from "../../lib/constants";
  import { sortObjectsByModel } from "../../lib/api/objectsApi";
  import PreAnnotation from "../PreAnnotation/PreAnnotation.svelte";
  import type { ObjectsSortedByModelType } from "../../lib/types/imageWorkspaceTypes";

  let allItemsSortedByModel: ObjectsSortedByModelType = {
    [GROUND_TRUTH]: [],
    [MODEL_RUN]: [],
    [PRE_ANNOTATION]: [],
  };
  let allIds: string[] = [];

  itemObjects.subscribe((value) => {
    allIds = value.map((item) => item.id);
    allItemsSortedByModel = sortObjectsByModel(value);
  });

  let colorScale = utils.ordinalColorScale(allIds);
</script>

<div class="p-2">
  <PreAnnotation {colorScale} />
  <div>
    <ObjectsModelSection sectionTitle={"Ground truth"} modelName={GROUND_TRUTH}>
      {#each allItemsSortedByModel[GROUND_TRUTH] as itemObject}
        <ObjectItem bind:itemObject {colorScale} />
      {/each}
    </ObjectsModelSection>
  </div>
  <ObjectsModelSection sectionTitle={"Model run"} modelName={MODEL_RUN}>
    {#each allItemsSortedByModel[MODEL_RUN] as model}
      <ObjectsModelSection sectionTitle={model.modelName} modelName={model.modelName}>
        {#each model.objects as itemObject}
          <ObjectItem bind:itemObject {colorScale} />
        {/each}
      </ObjectsModelSection>
    {/each}
  </ObjectsModelSection>
</div>
