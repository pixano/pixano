<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Combobox, cn, type ObjectThumbnail, Entity, Source } from "@pixano/core";
  import { Thumbnail } from "@pixano/canvas2d";

  import ObjectCard from "./ObjectCard.svelte";
  import ObjectsModelSection from "./ObjectsModelSection.svelte";
  import {
    annotations,
    entities,
    views,
    preAnnotationIsActive,
    itemMetas,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import { sourcesStore } from "../../../../../apps/pixano/src/lib/stores/datasetStores";
  import {
    createObjectCardId,
    defineObjectThumbnail,
    getTopEntity,
  } from "../../lib/api/objectsApi";
  import PreAnnotation from "../PreAnnotation/PreAnnotation.svelte";

  const allEntitiesSortedBySource: Record<string, Record<string, Entity[]>> = {};
  let sourceStruct: Record<string, Record<string, Source | undefined>> = {};
  let selectedModelId: string | undefined = undefined;
  let thumbnail: ObjectThumbnail | null = null;

  $: $annotations, $entities, handleAnnotationSortedByModel();

  const handleAnnotationSortedByModel = () => {
    //console.log("ObjectInspector refresh fired", $annotations, $entities);
    $annotations.forEach((ann) => {
      let kind: string = "other";
      let srcId: string = "unknown";
      let source: Source | undefined = undefined;
      if (ann.data.source_ref.id !== "") {
        source = $sourcesStore.find((src) => src.id === ann.data.source_ref.id);
        if (source) {
          kind = source.data.kind;
          srcId = source.id;
        } else {
          srcId = ann.data.source_ref.id;
        }
      } else {
        console.warn("No associated source !!", ann.data.source_ref);
      }
      if (!(kind in allEntitiesSortedBySource)) {
        allEntitiesSortedBySource[kind] = {};
        sourceStruct[kind] = {};
      }
      if (!(srcId in allEntitiesSortedBySource[kind])) {
        allEntitiesSortedBySource[kind][srcId] = [];
        sourceStruct[kind][srcId] = source;
      }
      const top_entity = getTopEntity(ann, $entities);
      if (allEntitiesSortedBySource[kind][srcId].indexOf(top_entity) < 0)
        allEntitiesSortedBySource[kind][srcId].push(top_entity);
    });
    if ("model" in allEntitiesSortedBySource) {
      selectedModelId = Object.keys(allEntitiesSortedBySource["model"])[0];
    }
    //svelte hack
    sourceStruct = sourceStruct;

    //scroll and set thumbnail to highlighted object if any
    const highlightedObject = $annotations.find((ann) => ann.ui.highlighted === "self");
    if (highlightedObject) {
      thumbnail = defineObjectThumbnail($itemMetas, $views, highlightedObject);
      const element = document.querySelector(`#${createObjectCardId(highlightedObject)}`);
      if (element) {
        element.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    } else {
      thumbnail = null;
    }
  };
</script>

<div class="p-2 h-[calc(100vh-200px)]">
  <PreAnnotation />
  {#if !$preAnnotationIsActive}
    <div
      class={cn("", {
        block: !thumbnail,
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
      {#key sourceStruct}
        {#each Object.keys(sourceStruct) as kind}
          {#if kind === "model" && selectedModelId}
            <ObjectsModelSection
              source={sourceStruct[kind][selectedModelId]}
              numberOfItem={allEntitiesSortedBySource[kind][selectedModelId].length}
            >
              <Combobox
                slot="modelSelection"
                bind:value={selectedModelId}
                width="w-[150px]"
                listItems={Object.keys(allEntitiesSortedBySource[kind]).map((sourceId) => ({
                  value: sourceId,
                  label: sourceId,
                }))}
              />
              {#each allEntitiesSortedBySource[kind][selectedModelId] as entity}
                <ObjectCard bind:entity />
              {/each}
            </ObjectsModelSection>
          {:else}
            {#each Object.keys(sourceStruct[kind]) as src_id}
              <ObjectsModelSection
                source={sourceStruct[kind][src_id]}
                numberOfItem={allEntitiesSortedBySource[kind][src_id].length}
              >
                {#each allEntitiesSortedBySource[kind][src_id] as entity}
                  <ObjectCard bind:entity />
                {/each}
              </ObjectsModelSection>
            {/each}
          {/if}
        {/each}
      {/key}
    </div>
  {/if}
</div>
