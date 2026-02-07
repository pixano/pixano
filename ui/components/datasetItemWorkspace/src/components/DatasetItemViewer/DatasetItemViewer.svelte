<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Loader2Icon } from "lucide-svelte";
  import { onDestroy } from "svelte";

  import {
    BaseSchema,
    LoadingModal,
    Mask,
    SequenceFrame,
    WorkspaceType,
    type Box,
    type DatasetItem,
    type LabeledClick,
    type Reference,
  } from "@pixano/core";
  import {
    pixanoInferenceToValidateTrackingMasks,
    pixanoInferenceTrackingNbAdditionalFrames,
    type PixanoInferenceSegmentationOutput,
    type PixanoInferenceVideoSegmentationOutput,
  } from "@pixano/core/src/components/pixano_inference_segmentation/inference";
  import {
    inferenceServerStore,
    segmentationModels,
    selectedSegmentationModelName,
  } from "@pixano/core/src/lib/stores/inferenceStore";
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

  let modelWorking: boolean = false;

  const unsubscribeModelsUiStore = modelsUiStore.subscribe(() => {
    if (selectedItem) loadViewEmbeddings();
  });

  onDestroy(unsubscribeModelsUiStore);

  const pixanoInferenceSegmentation = async (
    viewRef: Reference,
    points: LabeledClick[],
    box: Box,
  ): Promise<Mask | undefined> => {
    if (!$inferenceServerStore.connected) return;
    const maskModelName = $selectedSegmentationModelName ?? "SAM2";
    const selectedModel = $segmentationModels.find((m) => m.name === maskModelName);
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
      provider_name: selectedModel?.provider_name ?? undefined,
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
    modelWorking = true;
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
      modelWorking = false;
      return result.mask as Mask;
    } else {
      console.error("ERROR: Unable to segment", response);
      console.log("  error details:", await response.json());
    }
    modelWorking = false;
    return;
  };

  const pixanoInferenceSegmentationVideo = async (
    viewRef: Reference,
    points: LabeledClick[],
    box: Box,
  ): Promise<Mask | undefined> => {
    if (!$inferenceServerStore.connected) return;
    const maskModelName = $selectedSegmentationModelName ?? "SAM2_video";
    const selectedVideoModel = $segmentationModels.find((m) => m.name === maskModelName);

    //get video from viewRef (current frame) & num_frames
    let full_video = selectedItem.views[viewRef.name];
    if (!Array.isArray(full_video)) {
      console.error("Tracking available only for video!");
      return;
    }
    const first_frame = full_video.find((sf) => sf.id === viewRef.id) as SequenceFrame;
    if (!first_frame) {
      console.error("ERROR: frame unavailable");
      return;
    }
    const sub_video = full_video.filter(
      (sf) =>
        (sf as SequenceFrame).data.frame_index >= first_frame.data.frame_index &&
        (sf as SequenceFrame).data.frame_index <=
          first_frame.data.frame_index + $pixanoInferenceTrackingNbAdditionalFrames,
    );

    //need to remove "/media" from seqframes url, and move "data" outside !
    const video = sub_video.map((sf) => {
      const fixed_sf = structuredClone(sf);
      fixed_sf.data.url = (fixed_sf.data.url as string).replace("media/", "");
      return fixed_sf;
    });

    const base_input = {
      dataset_id: selectedItem.ui.datasetId,
      video,
      model: maskModelName,
      provider_name: selectedVideoModel?.provider_name ?? undefined,
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
    //console.log("INPUT:", input);
    modelWorking = true;
    const response = await fetch("/inference/tasks/mask-generation/video", {
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      method: "POST",
      body: JSON.stringify(input),
    });
    if (response.ok) {
      const result = (await response.json()) as PixanoInferenceVideoSegmentationOutput;
      //console.log("RAW OUTPUT", result);
      //TODO: rebuild
      for (const mask of result.masks) {
        mask.data.counts = rleFrString(mask.data.counts as string);
        //correct viewref..etc ?
      }
      //We will store masks so that when validated, they are used to fill the created Track
      pixanoInferenceToValidateTrackingMasks.set(result.masks);
      modelWorking = false;
      return result.masks[0] as Mask;
    } else {
      console.error("ERROR: Unable to track", response);
      console.log("  error details:", await response.json());
    }
    modelWorking = false;
    return;
  };
</script>

<div class="max-h-[calc(100vh-80px)] w-full max-w-full bg-foreground">
  {#if isLoading}
    <div class="h-full w-full flex justify-center items-center">
      <Loader2Icon class="animate-spin text-white" />
    </div>
  {:else if selectedItem.ui.type === WorkspaceType.VIDEO}
    <VideoViewer
      {selectedItem}
      pixanoInferenceSegmentation={pixanoInferenceSegmentationVideo}
      {resize}
      bind:currentAnn
    />
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
{#if modelWorking}
  <LoadingModal />
{/if}
