<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Combobox, cn, type ObjectThumbnail, Entity } from "@pixano/core";
  import { Thumbnail } from "@pixano/canvas2d";

  import ObjectCard from "./ObjectCard.svelte";
  import ObjectsModelSection from "./ObjectsModelSection.svelte";
  import {
    annotations,
    entities,
    preAnnotationIsActive,
    itemMetas,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import { GROUND_TRUTH, PRE_ANNOTATION } from "../../lib/constants";
  import {
    createObjectCardId,
    defineObjectThumbnail,
    sortObjectsByModel,
    getObjectEntity,
  } from "../../lib/api/objectsApi";
  import PreAnnotation from "../PreAnnotation/PreAnnotation.svelte";
  import type { ObjectsSortedByModelType } from "../../lib/types/datasetItemWorkspaceTypes";

  let allEntitiesSortedByModel: ObjectsSortedByModelType<Entity> = {
    [GROUND_TRUTH]: [],
    [PRE_ANNOTATION]: [],
  };

  let thumbnail: ObjectThumbnail | null = null;

  annotations.subscribe((objects) => {
    const highlightedObject = objects.find((item) => item.highlighted === "self");
    if (highlightedObject) {
      thumbnail = defineObjectThumbnail($itemMetas, highlightedObject);
    } else {
      thumbnail = null;
    }
  });

  annotations.subscribe((objects) => {
    const allAnnotationsSortedByModel = sortObjectsByModel(objects);
    //map allItems.. as Annotation to correspnding entities
    //allEntitiesSortedByModel = fct(allAnnotationsSortedByModel);
    for (const model in allAnnotationsSortedByModel) {
      allEntitiesSortedByModel[model] = allAnnotationsSortedByModel[model].map((ann) =>
        getObjectEntity(ann, $entities),
      );
    }

    const highlightedObject = objects.find((item) => item.highlighted === "self");
    if (!highlightedObject) return;
    const element = document.querySelector(`#${createObjectCardId(highlightedObject)}`);
    if (element) {
      element.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });

  let allModels = Object.keys(allEntitiesSortedByModel).filter(
    (model) => model !== GROUND_TRUTH && model !== PRE_ANNOTATION,
  );

  let selectedModel: string = Object.keys(allEntitiesSortedByModel).filter(
    (model) => model !== GROUND_TRUTH && model !== PRE_ANNOTATION,
  )[0];
</script>

<div class="p-2 flex flex-col h-[calc(100vh-200px)]">
  <PreAnnotation />
  {#if !$preAnnotationIsActive}
    <div
      class={cn("gap-4 grow grid grid-cols-1 grid-rows-2 h-full", {
        block: !thumbnail && !selectedModel,
        "grid-rows-[150px_80%]": thumbnail,
      })}
    >
      {#if thumbnail}
        {#key thumbnail.coords[0]}
          <Thumbnail
            imageDimension={thumbnail.baseImageDimensions}
            coords={thumbnail.coords}
            imageUrl={`/${thumbnail.uri}`}
            maxHeight={150}
            maxWidth={300}
          />
        {/key}
      {/if}
      <ObjectsModelSection
        sectionTitle="Ground truth"
        modelName={GROUND_TRUTH}
        numberOfItem={allEntitiesSortedByModel[GROUND_TRUTH].length}
      >
        {#each allEntitiesSortedByModel[GROUND_TRUTH] as entity}
          <ObjectCard bind:entity />
        {/each}
      </ObjectsModelSection>
      {#if selectedModel}
        <ObjectsModelSection
          sectionTitle="Model run"
          modelName={selectedModel}
          numberOfItem={allEntitiesSortedByModel[selectedModel]?.length || 0}
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
          {#each allEntitiesSortedByModel[selectedModel] || [] as entity}
            <ObjectCard bind:entity />
          {/each}
        </ObjectsModelSection>
      {/if}
    </div>
  {/if}
</div>
