<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Thumbnail } from "@pixano/canvas2d";
  import { BaseSchema, Annotation, cn, Entity, Source, type ObjectThumbnail } from "@pixano/core";

  import {
    createObjectCardId,
    defineObjectThumbnail,
    getTopEntity,
  } from "../../lib/api/objectsApi";
  import {
    annotations,
    entities,
    itemMetas,
    preAnnotationIsActive,
    views,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import PreAnnotation from "../PreAnnotation/PreAnnotation.svelte";
  import ObjectCard from "./ObjectCard.svelte";
  import ObjectsModelSection from "./ObjectsModelSection.svelte";

  let allTopEntities: Entity[];
  let selectedEntity: string;
  let thumbnail: ObjectThumbnail | null = null;

  //Note: Previously Entities where grouped by source
  //Now they're all displayed regardless of source
  //so we fake a global source for ObjectsModelSection (may be rewritten later)
  const now = new Date(Date.now()).toISOString().replace(/Z$/, "+00:00");
  const globalSource = new Source({
    id: "pixano_source",
    created_at: now,
    updated_at: now,
    table_info: { name: "source", group: "source", base_schema: BaseSchema.Source },
    data: { name: "All", kind: "Global", metadata: "{}" },
  });

  $: $annotations, $entities, handleAnnotationSortedByModel();

  const handleAnnotationSortedByModel = () => {
    //svelte hack: use a temp Set to set the whole list once
    const allTopEntitiesSet = new Set<Entity>();
    $annotations.forEach((ann) => {
      allTopEntitiesSet.add(getTopEntity(ann, $entities));
    });
    allTopEntities = Array.from(allTopEntitiesSet);
    //console.log("ObjectInspector refresh fired", $annotations, $entities, allTopEntities);

    //scroll and set thumbnail to highlighted object if any
    // const highlightedObject = $annotations.find((ann) => ann.ui.highlighted === "self");

    const highlightedBoxes: Annotation[] | undefined = $annotations.filter(
      (ann) => ann.ui.highlighted === "self" && ann.is_type(BaseSchema.BBox),
    );
    const highlightedObject: Annotation | undefined = highlightedBoxes
      ? highlightedBoxes[Math.round(highlightedBoxes.length / 2)]
      : undefined;

    if (highlightedObject) {
      selectedEntity = highlightedObject.data.entity_ref.id;
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

<div class="p-2 h-[calc(100vh-200px)] w-full">
  <PreAnnotation />
  {#if !$preAnnotationIsActive}
    <div
      class={cn({
        block: !thumbnail,
        "grid-rows-[150px_80%]": thumbnail,
      })}
    >
      {#if thumbnail}
        <span class="flex justify-center"> Selected object: {selectedEntity}</span>
        {#key thumbnail.coords[0]}
          <Thumbnail
            imageDimension={thumbnail.baseImageDimensions}
            coords={thumbnail.coords}
            imageUrl={`/${thumbnail.uri}`}
            minSide={150}
            maxHeight={200}
            maxWidth={200}
          />
        {/key}
      {/if}
      <ObjectsModelSection source={globalSource} numberOfItem={allTopEntities.length}>
        {#each allTopEntities as entity}
          <ObjectCard bind:entity />
        {/each}
      </ObjectsModelSection>
    </div>
  {/if}
</div>
