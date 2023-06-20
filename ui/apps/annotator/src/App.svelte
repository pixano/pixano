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
  import Library from "./lib/Library.svelte";
  import EmptyLibrary from "./lib/EmptyLibrary.svelte";
  import DatasetExplorer from "./lib/DatasetExplorer.svelte";
  import AnnotationWorkspace from "./lib/AnnotationWorkspace.svelte";
  import type { ItemData, MaskGT, AnnotationsLabels, ItemLabel } from "./lib/interfaces";
  import { SAM } from "../../../components/models/src/Sam";
  import * as ort from "onnxruntime-web";
  import * as npyjs from "../../../components/models/src/npy";

  import { interactiveSegmenterModel } from "./stores";

  import * as api from "./lib/api";
  //import type { InteractiveImageSegmenter } from "../../../components/models/src/interactive_image_segmentation";
  //import { MockInteractiveImageSegmenter } from "../../../tools/storybook/stories/components/canvas2d/mocks";

  import { generatePolygonSegments, convertSegmentsToSVG } from "../../../components/models/src/tracer";
  import Header from "./lib/Header.svelte";

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
    // const item = await api.getItemDetails("DKY9qXERsxQZ3qQ8RmEmcp", "285");
    // const item = await api.getItemDetails("gevmzZxvmt6rjd9zdmHctT", "aeroport-avions.jpg")
    // console.log(item);

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
    const embeddingArrByte = await api.getImageEmbedding(selectedDataset.id, itemDetails.id);
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

  onMount(async () => {
    datasets = await api.getDatasetsList();

    //await sam.init("/models/sam_onnx_quantized_vit_h.onnx");
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
      dataset={selectedDataset}
      on:imageSelected={selectItem}
    />
  {/if}
{:else}
  <Header bind:selectedDataset bind:selectedItem />
  <div class="pt-20">
    <Library {datasets} on:datasetclick={selectDataset} />
  </div>
{/if}
