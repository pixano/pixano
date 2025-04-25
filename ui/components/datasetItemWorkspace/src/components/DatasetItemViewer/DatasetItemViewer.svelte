<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Loader2Icon } from "lucide-svelte";

  import { api, BaseSchema, ImageTask, Mask, WorkspaceType, type DatasetItem } from "@pixano/core";
  import { pixanoInferenceModelsStore } from "@pixano/core/src/lib/types/inference/modelsStore";
  import type { InteractiveImageSegmenterOutput } from "@pixano/models";

  import { rleFrString } from "../../../../canvas2d/src/api/maskApi";
  import { loadViewEmbeddings } from "../../lib/api/modelsApi";
  import { getTopEntity } from "../../lib/api/objectsApi";
  import {
    annotations,
    entities,
    modelsUiStore,
  } from "../../lib/stores/datasetItemWorkspaceStores";
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

  //TEST -- it doesn't belong here -- but it's convenient for testing
  const SAM2Test = async () => {
    console.log(
      "THIS is a test!! -- requires at least one bbox (take the highlighted one) (used as input) and its entity (to put mask)",
    );
    console.time("timer");
    // NOTE: should create one (?), or change the way it works in back ?
    // eg. provide bbox id, and back just retrieve image, entity, and so on
    // anyway this is just a POC demonstrating that we can connect and infer with SAM2 with pixano-inference
    const isConnected = await api.isInferenceApiHealthy("http://localhost:9152");
    if (!isConnected) return;
    const models = await api.listModels();
    console.log("Models:", models);
    const selectedMaskModel = $pixanoInferenceModelsStore.find(
      (m) => m.task === ImageTask.MASK_GENERATION && m.selected,
    );
    const maskModelName = selectedMaskModel ? selectedMaskModel.name : "SAM2";
    if (!models.map((m) => m.name).includes(maskModelName)) return;
    //Note: for multiview, needs to have the view (can use bbox view_ref)
    //for video, need frame index (?) -> $currentFrameIndex --- and manage tracklets & co -- later ...
    const image = selectedItem.views[Object.keys(selectedItem.views)[0]];
    if (Array.isArray(image)) return;
    //need to remove "/media" from image url !
    const fixed_image = structuredClone(image);
    fixed_image.data.url = (fixed_image.data.url as string).replace("media/", "");

    const bbox = $annotations.find(
      (ann) => ann.is_type(BaseSchema.BBox) && ann.ui.displayControl.highlighted === "self",
    );
    const entity = bbox?.ui.top_entities![0];
    if (!bbox || !entity) {
      console.log("No highlighted bbox!");
      return;
    }
    const { ui: ui_e, ...entity_no_ui } = entity;
    const { ui: ui_b, ...bbox_no_ui } = bbox;
    //it wants an "classic entity with "data", but not for the bbox.. how painfull !!
    //reshape bbox as it is requested ...
    //make a copy...
    const bb = structuredClone(bbox_no_ui);
    const b_data = bb.data;
    const { data, ...bb_base } = bb;
    const requested_bbox = { ...bb_base, ...b_data };
    const input = {
      dataset_id: selectedItem.ui.datasetId,
      image: fixed_image,
      entity: entity_no_ui,
      model: maskModelName,
      bbox: requested_bbox,
      mask_table_name: "masks", //TODO : get correct masks table name
    };
    console.log("INPUT:", input);
    const response = await fetch("/inference/tasks/mask-generation/image", {
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      method: "POST",
      body: JSON.stringify(input),
    });
    if (response.ok) {
      const result = await response.json();
      const new_mask = new Mask(result.mask);
      new_mask.data.counts = rleFrString(new_mask.data.counts as string);
      annotations.update((anns) => {
        getTopEntity(new_mask); //set top entities;
        anns.push(new_mask);
        return anns;
      });
      entities.update((ents) =>
        ents.map((ent) => {
          if (ent.id === entity.id) {
            ent.ui.childs?.push(new_mask);
          }
          return ent;
        }),
      );
      //should add to save too, but it's just a test so... no :)
    } else {
      console.log("no answer!", response);
      console.log("...", await response.json());
    }
    console.timeEnd("timer");
  };

  //TMP TEST
  async function handleKeyDown(event: KeyboardEvent) {
    const activeElement = document.activeElement;
    if (
      activeElement instanceof HTMLInputElement ||
      activeElement instanceof HTMLTextAreaElement ||
      activeElement?.getAttribute("contenteditable") === "true"
    ) {
      return; // Ignore shortcut when typing text
    }
    if (event.key == "k") {
      await SAM2Test();
    }
  }
</script>

<div class="max-h-[calc(100vh-80px)] w-full max-w-full bg-slate-800">
  {#if isLoading}
    <div class="h-full w-full flex justify-center items-center">
      <Loader2Icon class="animate-spin text-white" />
    </div>
  {:else if selectedItem.ui.type === WorkspaceType.VIDEO}
    <VideoViewer {selectedItem} {resize} bind:currentAnn />
  {:else if selectedItem.ui.type === WorkspaceType.IMAGE_VQA}
    <VqaViewer {selectedItem} {resize} bind:currentAnn />
  {:else if selectedItem.ui.type === WorkspaceType.IMAGE_TEXT_ENTITY_LINKING}
    <EntityLinkingViewer {selectedItem} {resize} bind:currentAnn />
  {:else if selectedItem.ui.type === WorkspaceType.IMAGE || !selectedItem.ui.type}
    <ImageViewer {selectedItem} {resize} bind:currentAnn />
  {:else if selectedItem.ui.type === WorkspaceType.PCL_3D}
    <ThreeDimensionsViewer />
  {/if}
</div>
<svelte:window on:keydown={handleKeyDown} />
