<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Loader2Icon } from "lucide-svelte";

  import {
    api,
    BaseSchema,
    Mask,
    WorkspaceType,
    type Box,
    type DatasetItem,
    type LabeledClick,
    type Reference,
  } from "@pixano/core";
  import {
    pixanoInferenceSegmentationModelsStore,
    pixanoInferenceSegmentationURL,
    type PixanoInferenceSegmentationOutput,
  } from "@pixano/core/src/components/pixano_inference_segmentation/inference";
  import type { InteractiveImageSegmenterOutput } from "@pixano/models";

  import { rleFrString } from "../../../../canvas2d/src/api/maskApi";
  import { loadViewEmbeddings } from "../../lib/api/modelsApi";
  import { modelsUiStore } from "../../lib/stores/datasetItemWorkspaceStores";
  import ThreeDimensionsViewer from "./3DViewer.svelte";
  import EntityLinkingViewer from "./EntityLinkingViewer.svelte";
  import ImageViewer from "./ImageViewer.svelte";
  import VideoViewer from "./VideoViewer.svelte";
  import VqaViewer from "./VqaViewer.svelte";

  export let selectedItem: DatasetItem;
  export let currentAnn: InteractiveImageSegmenterOutput | null = null;
  export let isLoading: boolean;
  export let resize: number;

  modelsUiStore.subscribe(() => {
    if (selectedItem) loadViewEmbeddings();
  });

  const pixanoInferenceSegmentation = async (
    viewRef: Reference,
    points: LabeledClick[],
    box: Box,
  ): Promise<Mask | undefined> => {
    const isConnected = await api.isInferenceApiHealthy($pixanoInferenceSegmentationURL);
    if (!isConnected) return;
    const models = await api.listModels();
    const selectedMaskModel = $pixanoInferenceSegmentationModelsStore.find((m) => m.selected);
    const maskModelName = selectedMaskModel ? selectedMaskModel.name : "SAM2";
    if (!models.map((m) => m.name).includes(maskModelName)) return;
    let image = selectedItem.views[viewRef.name];
    if (Array.isArray(image)) {
      const candidate_image = image.find((v) => v.id === viewRef.id);
      if (candidate_image) image = candidate_image;
      else return;
    }
    //need to remove "/media" from image url !
    const fixed_image = structuredClone(image);
    fixed_image.data.url = (fixed_image.data.url as string).replace("media/", "");
    const base_input = {
      dataset_id: selectedItem.ui.datasetId,
      image: fixed_image,
      model: maskModelName,
      entity: null, //unused, we don't create a mask object, we only need the mask RLE
      mask_table_name: "", //unused, we don't create a mask object, we only need the mask RLE
    };
    let input;
    if (points) {
      let pts = [];
      let labels = [];
      for (const pt of points) {
        pts.push([Math.round(pt.x), Math.round(pt.y)]);
        labels.push(pt.label);
      }
      input = { ...base_input, points: pts, labels: labels };
    }
    if (box) {
      //coords must be positive
      const positiveBBox = (bbox: Box): Box => {
        let { x, y, width, height } = bbox;
        if (width < 0) {
          x += width;
          width = -width;
        }
        if (height < 0) {
          y += height;
          height = -height;
        }
        if (x < 0) {
          width += x;
          x = 0;
        }
        if (y < 0) {
          height += y;
          y = 0;
        }
        width = Math.max(0, width);
        height = Math.max(0, height);
        return { x, y, width, height } as Box;
      };
      box = positiveBBox(box);
      //need a somehow BBox object (not exactly).
      const now = new Date(Date.now()).toISOString().replace(/Z$/, "+00:00");
      const input_bbox = {
        id: "",
        created_at: now,
        updated_at: now,
        table_info: { name: "", group: "annotations", base_schema: BaseSchema.BBox },
        coords: [
          Math.round(box.x),
          Math.round(box.y),
          Math.round(box.width),
          Math.round(box.height),
        ],
        format: "xywh",
        is_normalized: false,
        confidence: 1,
      };
      input = { ...base_input, bbox: input_bbox };
    }
    const response = await fetch("/inference/tasks/mask-generation/image", {
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      method: "POST",
      body: JSON.stringify(input),
    });
    if (response.ok) {
      const result = (await response.json()) as PixanoInferenceSegmentationOutput;
      result.mask.data.counts = rleFrString(result.mask.data.counts as string);
      return result.mask as Mask;
    } else {
      console.error("ERROR: Unable to segment", response);
      console.log("  error details:", await response.json());
    }
    return;
  };
</script>

<div class="max-h-[calc(100vh-80px)] w-full max-w-full bg-slate-800">
  {#if isLoading}
    <div class="h-full w-full flex justify-center items-center">
      <Loader2Icon class="animate-spin text-white" />
    </div>
  {:else if selectedItem.ui.type === WorkspaceType.VIDEO}
    <VideoViewer {selectedItem} {pixanoInferenceSegmentation} {resize} bind:currentAnn />
  {:else if selectedItem.ui.type === WorkspaceType.IMAGE_VQA}
    <VqaViewer {selectedItem} {pixanoInferenceSegmentation} {resize} bind:currentAnn />
  {:else if selectedItem.ui.type === WorkspaceType.IMAGE_TEXT_ENTITY_LINKING}
    <EntityLinkingViewer {selectedItem} {pixanoInferenceSegmentation} {resize} bind:currentAnn />
  {:else if selectedItem.ui.type === WorkspaceType.IMAGE || !selectedItem.ui.type}
    <ImageViewer {selectedItem} {pixanoInferenceSegmentation} {resize} bind:currentAnn />
  {:else if selectedItem.ui.type === WorkspaceType.PCL_3D}
    <ThreeDimensionsViewer />
  {/if}
</div>
