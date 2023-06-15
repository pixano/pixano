<script lang="ts">
  /**
  @copyright CEA-LIST/DIASI/SIALV/LVA (2023)
  @author CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
  @license CECILL-C

  This software is a collaborative computer program whose purpose is to
  generate and explore labeled data for computer vision applications.
  This software is governed by the CeCILL-C license under French law and
  abiding by the rules of distribution of free software. You can use, 
  modify and/ or redistribute the software under the terms of the CeCILL-C
  license as circulated by CEA, CNRS and INRIA at the following URL

  http://www.cecill.info
  */

  // Imports
  import { onMount } from "svelte";
  import Header from "./lib/Header.svelte";
  import Library from "./lib/Library.svelte";
  import EmptyLibrary from "./lib/EmptyLibrary.svelte";
  import DatasetExplorer from "./lib/DatasetExplorer.svelte";
  import AnnotationWorkspace from "./lib/AnnotationWorkspace.svelte";
  import type { ItemData, MaskGT, AnnotationsLabels, ItemLabel } from "./lib/interfaces";
  import { generatePolygonSegments, convertSegmentsToSVG } from "../../../components/models/src/tracer";
  import { SAM } from "../../../components/models/src/Sam";
  import * as ort from "onnxruntime-web";
  import * as npyjs from "../../../components/models/src/npy";

  import { interactiveSegmenterModel } from "./stores";

  import * as api from "./lib/api";
  //import type { InteractiveImageSegmenter } from "../../../components/models/src/interactive_image_segmentation";
  //import { MockInteractiveImageSegmenter } from "../../../tools/storybook/stories/components/canvas2d/mocks";


  // Dataset navigation
  let datasets = null;
  let selectedDataset = null;

  let selectedItem: ItemData;
  let selectedItemEmbedding: any;

  let masksGT: Array<MaskGT> = [];
  let annotations: Array<AnnotationsLabels> = [];
  let classes = [];

  let showDetailsPage: boolean = false;

  let sam = new SAM();
  //let mock = new MockInteractiveImageSegmenter();

  async function selectDataset(event: CustomEvent) {
    selectedDataset = event.detail.dataset;
  }

  async function selectItem(event: CustomEvent) {

    showDetailsPage = true;
    const itemDetails = await api.getItemDetails(selectedDataset.id, event.detail.id);

    //selected item
    console.log("=== LOADING SELECTED ITEM ===");
    selectedItem = {
      dbName: selectedDataset.name,
      imageURL: itemDetails.views.image.image,
      imageId: event.detail.id,
      viewId: "image",
    };
    console.log("item loaded:", selectedItem);

    //build annotations, masksGT and classes

    //predefined classes from spec.json "categories"
    classes = selectedDataset.categories

    let struct_annotations = {}
    for (let i = 0; i < itemDetails.views.image.objects.id.length; ++i) {
      const mask_rle = itemDetails.views.image.objects.segmentation[i];
      const rle = mask_rle["counts"];
      const size = mask_rle["size"];
      const maskPolygons = generatePolygonSegments(rle, size[0]);
      const masksSVG = convertSegmentsToSVG(maskPolygons);

      masksGT.push({
        id: itemDetails.views.image.objects.id[i],
        mask: masksSVG,
        rle: mask_rle,
        visible: true
      });
      if(itemDetails.views.image.objects.category[i].name in struct_annotations) {
        const num = struct_annotations[itemDetails.views.image.objects.category[i].name].length;
        const item : ItemLabel = {
          id: itemDetails.views.image.objects.id[i],
          label: itemDetails.views.image.objects.category[i].name+"-"+num,
          visible: true
        }         
        struct_annotations[itemDetails.views.image.objects.category[i].name].push(item);
      } else {
        const item : ItemLabel = {
          id: itemDetails.views.image.objects.id[i],
          label: itemDetails.views.image.objects.category[i].name+"-0",
          visible: true
        }         
        struct_annotations[itemDetails.views.image.objects.category[i].name] = [item] 
      }
    }
    //convert struct to AnnotationsLabels
    for (let cls in struct_annotations) {
      annotations.push({
        class: cls, 
        items: struct_annotations[cls],
        visible: true
      });
      //classes from existing annotations
      classes.push({
        id: classes.length,
        name: cls
      })
    }

    // Embeddings
    console.log("=== LOADING EMBEDDING ===");
    const embeddingArrByte = await api.getImageEmbedding(selectedDataset.id, itemDetails.id, itemDetails.viewId);
    const embeddingArr = npyjs.parse(embeddingArrByte);
    selectedItemEmbedding = new ort.Tensor("float32", embeddingArr.data, embeddingArr.shape);
    console.log("Embedding:", selectedItemEmbedding);
    console.log("DONE");
  }

  function unselectItem() {
    showDetailsPage = false;
    selectedItem = null;
    masksGT = [];
    annotations = [];
    classes = [];
  }

  function findCategoryForId(anns: Array<AnnotationsLabels>, id: string) : string {
    for (let ann of anns) {
      if (ann.items.some(it=> it.id === id)) {
        return ann.class;
      }
    }
    console.log("ERROR - unable to find category for id:", id);
    return "undefined"; 
  }

  function saveAnns(data) {
    console.log("App - save annotations");
    console.log("data", data.detail);
    //format annotation data for export
    let anns = [];
    for(let mask of data.detail.masks) {
      const category = findCategoryForId(data.detail.anns, mask.id);
      let ann = {
        id: mask.id,
        category_name: category,
        mask: mask.rle,
      };
      anns.push(ann)
    }
    api.postAnnotations(anns, selectedDataset.id, selectedItem.imageId, selectedItem.viewId);
  }

  onMount(async () => {
    datasets = await api.getDatasetsList();

    //TODO: const model = await getModel();
    await sam.init("/models/sam_vit_h_4b8939.onnx");

    interactiveSegmenterModel.set(sam);
    //console.log("SAM input names:", sam.inputNames());
  });
</script>

{#if !datasets}
  <Header bind:selectedDataset bind:selectedItem />
  <div class="pt-20">
    <EmptyLibrary />
  </div>
{:else if selectedDataset}
  {#if !showDetailsPage}
    <Header bind:selectedDataset bind:selectedItem />
    <div class="pt-20">
      <DatasetExplorer dataset={selectedDataset} on:itemclick={selectItem} />
    </div>
  {:else if selectedItem}
    <AnnotationWorkspace
      itemData={selectedItem}
      embedding={selectedItemEmbedding}
      {annotations}
      {masksGT}
      {classes}
      handleCloseClick={unselectItem}
      on:saveAnns={saveAnns}
    />
  {/if}
{:else}
  <Header bind:selectedDataset bind:selectedItem />
  <div class="pt-20">
    <Library {datasets} on:datasetclick={selectDataset} />
  </div>
{/if}
