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

  import { utils, Combobox } from "@pixano/core";

  import ObjectItem from "./ObjectItem.svelte";
  import ObjectsModelSection from "./ObjectsModelSection.svelte";
  import { itemObjects } from "../../lib/stores/imageWorkspaceStores";
  import { GROUND_TRUTH, MODEL_RUN, PRE_ANNOTATION } from "../../lib/constants";
  import { sortObjectsByModel } from "../../lib/api/objectsApi";
  import PreAnnotation from "../PreAnnotation/PreAnnotation.svelte";
  import type { ObjectsSortedByModelType } from "../../lib/types/imageWorkspaceTypes";

  let allItemsSortedByModel: ObjectsSortedByModelType = {
    [GROUND_TRUTH]: [],
    [PRE_ANNOTATION]: [],
  };
  let allIds: string[] = [];

  itemObjects.subscribe((value) => {
    allIds = value.map((item) => item.id);
    allItemsSortedByModel = sortObjectsByModel(value);
  });

  let colorScale = utils.ordinalColorScale(allIds);
  let allModels = Object.keys(allItemsSortedByModel).filter(
    (model) => model !== GROUND_TRUTH && model !== PRE_ANNOTATION,
  );
  let selectedModel: string = Object.keys(allItemsSortedByModel).filter(
    (model) => model !== GROUND_TRUTH && model !== PRE_ANNOTATION,
  )[0];
</script>

<div class="p-2 flex flex-col h-full">
  <PreAnnotation {colorScale} />
  <div class="gap-4 grow grid grid-cols-1 grid-rows-2">
    <ObjectsModelSection
      sectionTitle="Ground truth"
      modelName={GROUND_TRUTH}
      numberOfItem={allItemsSortedByModel[GROUND_TRUTH].length}
    >
      {#each allItemsSortedByModel[GROUND_TRUTH] as itemObject}
        <ObjectItem bind:itemObject {colorScale} />
      {/each}
    </ObjectsModelSection>
    {#if selectedModel}
      <ObjectsModelSection
        sectionTitle="Model run"
        modelName={MODEL_RUN}
        numberOfItem={allItemsSortedByModel[selectedModel].length}
      >
        <Combobox
          slot="modelSelection"
          bind:value={selectedModel}
          width="w-[180px]"
          listItems={allModels.map((model) => ({
            value: model,
            label: model,
          }))}
        />
        {#each allItemsSortedByModel[selectedModel] || [] as itemObject}
          <ObjectItem bind:itemObject {colorScale} />
        {/each}
      </ObjectsModelSection>
    {/if}
  </div>
</div>
