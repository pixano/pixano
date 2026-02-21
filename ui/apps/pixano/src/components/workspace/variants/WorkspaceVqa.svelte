<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">

  // Imports
  import { untrack } from "svelte";
  import { Loader2Icon } from "lucide-svelte";

  import { Canvas2D } from "$components/workspace/canvas2d";
  import type { ImageFilters, Shape } from "$lib/types/shapeTypes";
  import {
    BaseSchema,
    DatasetItem,
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
  } from "../vqaCanvas";
  // Import stores and API functions
  import { inferenceServerStore, vqaModels } from "$lib/stores/inferenceStores.svelte";
  import { completionModelsStore } from "$lib/stores/vqaStores.svelte";

  import { applyNewShapeEditing } from "$lib/utils/entityMutations";
  import { loadImagesFromViews } from "$lib/utils/imageLoadUtils";
  import {
    brushSettings,
    colorScale,
    embeddings,
    entities,
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
    selectedItem: DatasetItem;
    resize: number;
  }

  let { selectedItem, resize }: Props = $props();

  // utility vars for resizing with slide bar
  let vqaAreaMaxWidth = $state(500); //default width
  const minVqaAreaWidth = 260; //minimum width for VqaArea (less may hide some elements)
  let expanding = $state(false);

  // Images per view type
  let imagesPerView: LoadedImagesPerView = $state({});
  let loaded: boolean = $state(false); // Loading status of images per view

  let isGenerating: boolean = $state(false);

  /**
   * Update the images based on the selected item views.
   */
  const updateImages = async (): Promise<void> => {
    if (selectedItem.views) {
      loaded = false;
      embeddings.value = {};
      modelsUiStore.update((store) => ({ ...store, yetToLoadEmbedding: true }));
      imagesPerView = await loadImagesFromViews(
        selectedItem.views as Record<string, Image>,
        { unwrapArrays: true },
      );
      loaded = true;
    }
  };

  // Reactive statement to update images when selectedItem changes or the 16 bit filters change
  let prev16BitRange: number[] = $state([]);
  $effect(() => {
    if (selectedItem || filters.value.u16BitRange) {
      if (
        prev16BitRange[0] !== filters.value.u16BitRange[0] ||
        prev16BitRange[1] !== filters.value.u16BitRange[1]
      ) {
        updateImages().catch(() => {
          console.error("Error loading the images.");
        });
        prev16BitRange = [...filters.value.u16BitRange];
      }
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

  const handleStoreQuestion = (event: StoreQuestionEvent) => {
    const conversationEntities = entities.value.filter((e) => e.is_type(BaseSchema.Conversation));

    if (conversationEntities.length === 0) {
      console.error("ERROR: No conversation entity found");
      return;
    }

    addQuestion({ newQuestionData: event, parentEntity: conversationEntities[0] });
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
    await generateAnswer(completionModel, question);
    isGenerating = false;
  };

  const expand = (e: MouseEvent) => {
    if (expanding) {
      vqaAreaMaxWidth = Math.max(e.pageX, minVqaAreaWidth);
    }
  };
</script>

<!-- Render the Canvas2D component with the loaded images or show a loading spinner -->
{#if loaded}
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
        onCompletionModelsChange={(models) => { completionModelsStore.value = models; }}
        onAnswerContentChange={handleAnswerContentChange}
        onStoreQuestion={handleStoreQuestion}
        onGenerateAnswer={handleGenerateAnswer}
        onDeleteQuestion={handleDeleteQuestion}
        onGenerateQuestion={generateQuestion}
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
    <div class="overflow-hidden grow">
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
        newShape={newShape.value as Shape}
        onSelectedToolChange={(tool) => selectedTool.value = tool}
        onNewShapeChange={(shape) => newShape.value = shape as import("$lib/ui").Shape}
        onBrushSettingsChange={(settings) => brushSettings.value = settings}
      />
    </div>
  </div>
{:else}
  <div class="w-full h-full flex items-center justify-center">
    <Loader2Icon class="h-10 w-10 animate-spin stroke-white" />
  </div>
{/if}
{#if isGenerating}
  <LoadingModal />
{/if}
