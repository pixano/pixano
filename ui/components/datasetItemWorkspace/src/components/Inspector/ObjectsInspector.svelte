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

  import { utils, Combobox, cn } from "@pixano/core";

  import ObjectCard from "./ObjectCard.svelte";
  import ObjectsModelSection from "./ObjectsModelSection.svelte";
  import { itemObjects, preAnnotationIsActive } from "../../lib/stores/datasetItemWorkspaceStores";
  import { GROUND_TRUTH, PRE_ANNOTATION } from "../../lib/constants";
  import { createObjectCardId, sortObjectsByModel } from "../../lib/api/objectsApi";
  import PreAnnotation from "../PreAnnotation/PreAnnotation.svelte";
  import type { ObjectsSortedByModelType } from "../../lib/types/datasetItemWorkspaceTypes";

  let allItemsSortedByModel: ObjectsSortedByModelType = {
    [GROUND_TRUTH]: [],
    [PRE_ANNOTATION]: [],
  };
  let allIds: string[] = [];

  itemObjects.subscribe((value) => {
    allIds = value.map((item) => item.id);
    allItemsSortedByModel = sortObjectsByModel(value);
    const highlightedObject = value.find((item) => item.highlighted === "self");
    if (!highlightedObject) return;
    const element = document.querySelector(`#${createObjectCardId(highlightedObject)}`);
    if (element) {
      element.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });

  let colorScale = utils.ordinalColorScale(allIds);

  let allModels = Object.keys(allItemsSortedByModel).filter(
    (model) => model !== GROUND_TRUTH && model !== PRE_ANNOTATION,
  );

  let selectedModel: string = Object.keys(allItemsSortedByModel).filter(
    (model) => model !== GROUND_TRUTH && model !== PRE_ANNOTATION,
  )[0];
</script>

<div class="p-2 flex flex-col h-[calc(100vh-200px)]">
  <PreAnnotation {colorScale} />
  {#if !$preAnnotationIsActive}
    <div
      class={cn("gap-4 grow grid grid-cols-1 grid-rows-2 h-full", {
        block: !selectedModel,
      })}
    >
      <ObjectsModelSection
        sectionTitle="Ground truth"
        modelName={GROUND_TRUTH}
        numberOfItem={allItemsSortedByModel[GROUND_TRUTH].length}
      >
        {#each allItemsSortedByModel[GROUND_TRUTH] as itemObject}
          <ObjectCard bind:itemObject {colorScale} />
        {/each}
      </ObjectsModelSection>
      {#if selectedModel}
        <ObjectsModelSection
          sectionTitle="Model run"
          modelName={selectedModel}
          numberOfItem={allItemsSortedByModel[selectedModel]?.length || 0}
        >
          <Combobox
            slot="modelSelection"
            bind:value={selectedModel}
            width="w-[150px]"
            listItems={allModels.map((model) => ({
              value: model,
              label: model,
            }))}
          />
          {#each allItemsSortedByModel[selectedModel] || [] as itemObject}
            <ObjectCard bind:itemObject {colorScale} />
          {/each}
        </ObjectsModelSection>
      {/if}
    </div>
  {/if}
</div>
