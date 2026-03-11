<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">

  // Imports
  import { nanoid } from "nanoid";
  import { untrack } from "svelte";
  import { Loader2Icon } from "lucide-svelte";

  import { Canvas2D } from "$components/workspace/canvas2d";
  import type { SelectionTool } from "$lib/tools";
  import type { ImageFilters, Shape } from "$lib/types/shapeTypes";
  import type { WorkspaceViewerItem } from "$lib/types/workspace";
  import {
    Image,
    LoadingModal,
    effectProbe,
    type LoadedImagesPerView,
  } from "$lib/ui";
  import {
    VqaArea,
    isNewAnswerEvent,
    isUpdatedMessageEvent,
    type ContentChangeEvent,
    type DeleteQuestionEvent,
    type GenerateAnswerEvent,
    type StoreQuestionEvent,
    type VqaMessageContext,
  } from "../vqaCanvas";
  // Import stores and API functions
  import { inferenceServerStore, vqaModels } from "$lib/stores/inferenceStores.svelte";
  import {
    completionModelsStore,
    type PixanoInferenceCompletionModel,
  } from "$lib/stores/vqaStores.svelte";

  import { applyNewShapeEditing } from "$lib/utils/entityAnnotationEditing";
  import { loadImagesFromViews } from "$lib/utils/imageLoadUtils";
  import {
    brushSettings,
    colorScale,
    embeddings,
    filters,
    imageSmoothing,
    itemBboxes,
    itemKeypoints,
    itemMasks,
    messages,
    modelsUiStore,
    newShape,
    preAnnotationIsActive,
    selectedTool,
  } from "$lib/stores/workspaceStores.svelte";
  import { addAnswer, addQuestion, deleteQuestion, generateAnswer, generateQuestion, updateMessageContent } from "$lib/stores/workspaceMutations";


  interface Props {
    // Attributes
    selectedItem: WorkspaceViewerItem;
    resize: number;
  }

  interface BrushSettings {
    brushRadius: number;
    lazyRadius: number;
    friction: number;
  }

  let { selectedItem, resize }: Props = $props();

  // utility vars for resizing with slide bar
  let vqaAreaMaxWidth = $state(500); //default width
  const minVqaAreaWidth = 260; //minimum width for VqaArea (less may hide some elements)
  let expanding = $state(false);

  // Images per view type
  let imagesPerView: LoadedImagesPerView = $state({});
  let loaded: boolean = $state(false); // Loading status of images per view
  let prevSelectedItemId: string = $state("");
  let imageLoadRequestId = 0;
  const hasImages = $derived(Object.keys(imagesPerView).length > 0);

  let isGenerating: boolean = $state(false);

  const handleCanvasShapeChange = (shape: Shape) => {
    if (shape.status === "creating") return;
    newShape.value = shape as import("$lib/ui").Shape;
  };

  /**
   * Update the images based on the selected item views.
   */
  const updateImages = async (clearExistingViews = false): Promise<void> => {
    const requestId = ++imageLoadRequestId;
    loaded = false;
    if (clearExistingViews) {
      imagesPerView = {};
    }

    if (!selectedItem.views) {
      imagesPerView = {};
      loaded = true;
      return;
    }

    embeddings.value = {};
    modelsUiStore.update((store) => ({ ...store, yetToLoadEmbedding: true }));
    const nextImages = await loadImagesFromViews(
      selectedItem.views as Record<string, Image>,
      { unwrapArrays: true, filterImages: true, sortKeys: true },
    );

    if (requestId !== imageLoadRequestId) return;
    imagesPerView = nextImages;
    loaded = true;
  };

  // Reactive statement to update images when selectedItem changes or the 16 bit filters change
  let prev16BitRange = $state<number[]>([0, 0]);
  $effect(() => {
    const selectedItemId = selectedItem?.item?.id ?? "";
    const next16BitRange = filters.value.u16BitRange;
    const itemChanged = selectedItemId !== prevSelectedItemId;
    const rangeChanged =
      prev16BitRange[0] !== next16BitRange[0] || prev16BitRange[1] !== next16BitRange[1];

    if (itemChanged || rangeChanged) {
      prevSelectedItemId = selectedItemId;
      prev16BitRange = [...next16BitRange];
      void updateImages(itemChanged).catch(() => {
        console.error("Error loading the images.");
      });
    }
  });

  // Reactive statement to update item objects when new shape is being edited and pre-annotation is not active
  $effect(() => {
    const shape = newShape.value;
    const isPreAnnotation = preAnnotationIsActive.value;
    if (shape?.status === "editing" && !isPreAnnotation) {
      untrack(() => {
        effectProbe("VqaViewer.applyNewShape", {
          status: shape?.status ?? "none",
          preAnnotationIsActive: isPreAnnotation,
        });
        applyNewShapeEditing(shape);
      });
    }
  });

  const handleAnswerContentChange = (event: ContentChangeEvent) => {
    if (isNewAnswerEvent(event)) {
      addAnswer(event);
    } else if (isUpdatedMessageEvent(event)) {
      updateMessageContent(event);
    }
  };

  const getImageViewContext = (): Pick<VqaMessageContext, "recordId" | "viewId" | "entityIds" | "imageUrl"> | null => {
    const recordId = selectedItem.item.id;
    for (const view of Object.values(selectedItem.views)) {
      if (!Array.isArray(view) && typeof view.data.url === "string" && view.data.url !== "") {
        return {
          recordId,
          viewId: view.id,
          entityIds: [],
          imageUrl: view.data.url,
        };
      }
    }
    return null;
  };

  const createNewConversationContext = (): VqaMessageContext | null => {
    const baseContext = getImageViewContext();
    if (!baseContext) return null;
    return {
      ...baseContext,
      conversationId: nanoid(22),
    };
  };

  const handleStoreQuestion = (event: StoreQuestionEvent) => {
    const context = createNewConversationContext();
    if (!context) {
      console.error("ERROR: No image view context found for VQA message creation");
      return;
    }

    addQuestion({ newQuestionData: event, context });
  };

  const handleDeleteQuestion = (event: DeleteQuestionEvent) => {
    deleteQuestion(event);
  };

  const handleGenerateAnswer = async (event: GenerateAnswerEvent) => {
    const { questionId, completionModel } = event;

    const question = messages.value.find((m) => m.id === questionId);

    if (question === undefined) {
      console.error("ERROR: Message not found");
      return;
    }
    isGenerating = true;
    const imageContext = getImageViewContext();
    await generateAnswer(completionModel, question, imageContext?.imageUrl ?? "");
    isGenerating = false;
  };

  const handleGenerateQuestion = async (completionModel: string) => {
    const context = createNewConversationContext();
    if (!context) {
      console.error("ERROR: No image view context found for VQA question generation");
      return null;
    }
    return generateQuestion(completionModel, context);
  };

  const expand = (e: MouseEvent) => {
    if (expanding) {
      vqaAreaMaxWidth = Math.max(e.pageX, minVqaAreaWidth);
    }
  };
</script>

<div
  class="h-full flex"
  onmouseup={() => {
    expanding = false;
  }}
  onmousemove={expand}
  role="tab"
  tabindex="0"
>
  <div class="w-full grow overflow-hidden" style={`max-width: ${vqaAreaMaxWidth}px`}>
    <VqaArea
      messages={messages.value}
      vqaSectionWidth={vqaAreaMaxWidth}
      inferenceServer={inferenceServerStore.value}
      vqaModels={vqaModels.value}
      completionModels={completionModelsStore.value}
      onCompletionModelsChange={(models: PixanoInferenceCompletionModel[]) => {
        completionModelsStore.value = models;
      }}
      onAnswerContentChange={handleAnswerContentChange}
      onStoreQuestion={handleStoreQuestion}
      onGenerateAnswer={handleGenerateAnswer}
      onDeleteQuestion={handleDeleteQuestion}
      onGenerateQuestion={handleGenerateQuestion}
    />
  </div>
  <button
    type="button"
    aria-label="Resize VQA and image panels"
    class="w-1 bg-primary-light cursor-col-resize h-full"
    onmousedown={() => {
      expanding = true;
    }}
></button>
  <div class="overflow-hidden grow relative">
    {#if loaded && hasImages}
      <Canvas2D
        {imagesPerView}
        selectedItemId={selectedItem.item.id}
        colorScale={colorScale.value[1]}
        bboxes={itemBboxes.value}
        masks={itemMasks.value}
        keypoints={itemKeypoints.value}
        filters={filters.value as ImageFilters}
        canvasSize={vqaAreaMaxWidth + resize}
        imageSmoothing={imageSmoothing.value}
        selectedTool={selectedTool.value}
        brushSettings={brushSettings.value}
        newShape={newShape.value}
        onSelectedToolChange={(tool: SelectionTool) => selectedTool.value = tool}
        onNewShapeChange={handleCanvasShapeChange}
        onBrushSettingsChange={(settings: BrushSettings) => brushSettings.value = settings}
      />
    {:else}
      <div class="w-full h-full bg-canvas"></div>
    {/if}

    {#if !loaded}
      <div class="absolute inset-0 z-10 bg-canvas/95 flex items-center justify-center">
        <Loader2Icon class="h-10 w-10 animate-spin stroke-white" />
      </div>
    {/if}
  </div>
</div>
{#if isGenerating}
  <LoadingModal />
{/if}
