<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Select } from "bits-ui";
  import {
    CaretDown,
    Chat,
    Check,
    CheckCircle,
    Gear,
    ListNumbers,
    PaperPlaneRight,
    Sparkle,
    Terminal,
  } from "phosphor-svelte";
  import { untrack } from "svelte";

  import ConfigurePromptModal from "../manageModels/ConfigurePromptModal.svelte";
  import PromptDebugModal from "../manageModels/PromptDebugModal.svelte";
  import { serializeMessageContent } from "./utils/serializeMessageContent";
  import { selectedVqaModel } from "$lib/stores/inferenceStores.svelte";
  import {
    lastVlmPromptStore,
    type PixanoInferenceCompletionModel,
  } from "$lib/stores/vqaStores.svelte";
  import { QuestionTypeEnum, type Message } from "$lib/types/dataset";
  import {
    getInferenceModelKey,
    type InferenceModel,
    type InferenceModelSelection,
    type InferenceServerState,
  } from "$lib/types/inference";
  import type { LabelFormat, StoreQuestionEvent } from "$lib/types/vqa";
  import {
    ContentChangeEventType,
    type ContentChangeEvent,
    type GenerateAnswerEvent,
  } from "$lib/types/vqa";
  import { AiProcessingBadge, AutoResizeTextarea, cn, IconButton, ModelSelectBadge } from "$lib/ui";
  import { effectProbe } from "$lib/utils/effectProbe";

  interface Props {
    pendingQuestion?: Message | null;
    inferenceServer: InferenceServerState;
    vqaModels: InferenceModel[];
    completionModels: PixanoInferenceCompletionModel[];
    onCompletionModelsChange?: (models: PixanoInferenceCompletionModel[]) => void;
    onStoreQuestion?: (event: StoreQuestionEvent) => void;
    onAnswerContentChange?: (event: ContentChangeEvent) => void;
    onGenerateAnswer?: (event: GenerateAnswerEvent) => Promise<string | null>;
    onGenerateQuestion?: (
      completionModel: InferenceModelSelection,
      questionType: QuestionTypeEnum,
    ) => Promise<{ content: string; choices: string[]; question_type: QuestionTypeEnum } | null>;
    pendingInputText?: string;
  }

  let {
    pendingQuestion = null,
    inferenceServer,
    vqaModels,
    completionModels,
    onCompletionModelsChange,
    onStoreQuestion,
    onAnswerContentChange,
    onGenerateAnswer,
    onGenerateQuestion,
    pendingInputText = $bindable(""),
  }: Props = $props();

  let questionContent = $state("");
  let questionType = $state(QuestionTypeEnum.OPEN);
  let isGenerating = $state(false);

  // Consume text pushed from sibling components (e.g. QuestionForm sparkle button)
  $effect(() => {
    if (pendingInputText) {
      questionContent = pendingInputText;
      pendingInputText = "";
    }
  });
  let selectedModel = $state("");
  let showPromptModal = $state(false);
  let showDebugModal = $state(false);
  let isQuestionTypeOpen = $state(false);

  let completionModel = $derived(completionModels.find((m) => m.selected));
  let isAnswering = $derived(!!pendingQuestion);

  let inferenceModels = $derived(
    vqaModels.map((m) => ({
      id: getInferenceModelKey(m),
      selection: { name: m.name, provider_name: m.provider_name },
    })),
  );

  let vqaModelLabel: string = $derived.by(() => {
    const entry = inferenceModels.find((m) => m.id === selectedModel);
    if (entry) return entry.selection.name;
    if (!inferenceServer.connected) return "No server";
    if (inferenceModels.length === 0) return "No models";
    return "Select model";
  });

  // Sync selected model to store and completion models
  $effect(() => {
    const model = selectedModel;
    const models = inferenceModels;
    if (!model && models.length === 0) return;
    untrack(() => {
      effectProbe("VqaInputArea.syncSelectedModel", {
        selectedModel: model,
        modelCount: models.length,
      });
      if (!model) {
        if (selectedVqaModel.value !== null) selectedVqaModel.value = null;
        return;
      }
      let hasSelectionChange = false;
      const nextModels = completionModels.map((m) => {
        const shouldSelect = getInferenceModelKey(m) === model;
        if (m.selected === shouldSelect) return m;
        hasSelectionChange = true;
        return { ...m, selected: shouldSelect };
      });
      const selectedInferenceModel = models.find((entry) => entry.id === model)?.selection ?? null;
      selectedVqaModel.value = selectedInferenceModel;
      if (hasSelectionChange) onCompletionModelsChange?.(nextModels);
    });
  });

  // Auto-select first model when none is selected
  $effect(() => {
    const models = inferenceModels;
    if (models.length === 0) return;
    untrack(() => {
      effectProbe("VqaInputArea.autoselect", {
        selectedModel,
        modelCount: models.length,
      });
      const hasSelection = models.some((model) => model.id === selectedModel);
      if (hasSelection) return;
      const currentSelection = selectedVqaModel.value;
      const currentSelectionId = currentSelection ? getInferenceModelKey(currentSelection) : "";
      selectedModel =
        models.find((model) => model.id === currentSelectionId)?.id ?? models[0]?.id ?? "";
    });
  });

  // Question type options
  const questionTypes = [
    { value: QuestionTypeEnum.OPEN, label: "Open", icon: Chat },
    { value: QuestionTypeEnum.SINGLE_CHOICE, label: "Yes / No", icon: CheckCircle },
    { value: QuestionTypeEnum.MULTI_CHOICE, label: "Multiple", icon: ListNumbers },
  ];

  let questionTypeItems = questionTypes.map((t) => ({ value: t.value, label: t.label }));

  let selectedTypeEntry = $derived(
    questionTypes.find((t) => t.value === questionType) ?? questionTypes[0],
  );

  let questionTypeChipClass = $derived(
    cn(
      "inline-flex h-7 items-center gap-1.5 rounded-full border px-2.5 text-[11px] font-normal shadow-sm backdrop-blur-sm transition-all duration-200",
      "bg-background/82 text-foreground border-border/45",
      "hover:bg-background/96 hover:border-border/70 hover:shadow-md",
      {
        "border-primary/35 bg-primary/8 shadow-[0_6px_18px_hsl(var(--primary)/0.12)]":
          isQuestionTypeOpen,
      },
    ),
  );

  const parseQuestionInput = (
    text: string,
  ): { content: string; choices: string[]; labelFormat: LabelFormat } => {
    const lines = text
      .split("\n")
      .map((l) => l.trim())
      .filter((l) => l !== "");
    if (lines.length <= 1) return { content: text, choices: [], labelFormat: "none" };

    const questionContent = lines[0];
    const potentialChoices = lines.slice(1);

    const numericRegex = /^[0-9]+[.)]\s*(.*)/;
    const alphaLowerRegex = /^[a-z][.)]\s*(.*)/;
    const alphaUpperRegex = /^[A-Z][.)]\s*(.*)/;
    const bulletRegex = /^[-*]\s*(.*)/;

    const firstLine = potentialChoices[0];
    let labelFormat: LabelFormat = "none";
    if (numericRegex.test(firstLine)) labelFormat = "numeric";
    else if (alphaLowerRegex.test(firstLine)) labelFormat = "alpha_lower";
    else if (alphaUpperRegex.test(firstLine)) labelFormat = "alpha_upper";
    else if (bulletRegex.test(firstLine)) labelFormat = "none";

    const choiceRegex = /^([0-9]+[.)]|[a-zA-Z][.)]|[-*])\s*(.*)/;
    const extractedChoices = potentialChoices.map((line) => {
      const match = line.match(choiceRegex);
      return match ? match[2].trim() : line;
    });

    return {
      content: questionContent,
      choices: extractedChoices,
      labelFormat,
    };
  };

  const handleSend = () => {
    const content = questionContent.trim();
    if (content === "") return;

    let finalContent = content;

    if (isAnswering && pendingQuestion) {
      const pqType = pendingQuestion.data.question_type;
      const isSingleChoice =
        pqType === QuestionTypeEnum.SINGLE_CHOICE ||
        pqType === QuestionTypeEnum.SINGLE_CHOICE_EXPLANATION;
      const isMultiChoice =
        pqType === QuestionTypeEnum.MULTI_CHOICE ||
        pqType === QuestionTypeEnum.MULTI_CHOICE_EXPLANATION;
      const choices = (pendingQuestion.data.choices as string[]) || [];
      const labelFormat =
        ((pendingQuestion.ui as Record<string, unknown>)?.labelFormat as LabelFormat | undefined) ??
        (isSingleChoice ? "none" : "alpha_upper");

      if (isSingleChoice || isMultiChoice) {
        const lowerContent = content.toLowerCase();
        let selectedIndices: number[] = [];

        if (isSingleChoice) {
          if (
            lowerContent === "y" ||
            lowerContent === "yes" ||
            lowerContent.startsWith("y ") ||
            lowerContent.startsWith("yes ")
          ) {
            selectedIndices = [0];
          } else if (
            lowerContent === "n" ||
            lowerContent === "no" ||
            lowerContent.startsWith("n ") ||
            lowerContent.startsWith("no ")
          ) {
            selectedIndices = [1];
          }
        }

        if (selectedIndices.length === 0) {
          const parts = content
            .split(/[,\s]+/)
            .map((p) => p.trim())
            .filter((p) => p !== "");
          const candidateIndices: number[] = [];

          for (const part of parts) {
            let foundIndex = -1;
            if (labelFormat === "numeric") {
              const num = parseInt(part, 10);
              if (!isNaN(num) && num > 0 && num <= choices.length) foundIndex = num - 1;
            } else if (labelFormat === "alpha_lower") {
              if (part.length === 1) {
                const code = part.toLowerCase().charCodeAt(0) - 97;
                if (code >= 0 && code < choices.length) foundIndex = code;
              }
            } else if (labelFormat === "alpha_upper" || labelFormat === undefined) {
              if (part.length === 1) {
                const code = part.toUpperCase().charCodeAt(0) - 65;
                if (code >= 0 && code < choices.length) foundIndex = code;
              }
            }

            if (foundIndex !== -1) {
              candidateIndices.push(foundIndex);
              if (isSingleChoice) break;
            }
          }

          if (candidateIndices.length > 0) {
            selectedIndices = candidateIndices;
          }
        }

        if (selectedIndices.length > 0) {
          const labels = selectedIndices.map((i) => String.fromCharCode(i + 65));
          const explanation = content.replace(/^(yes|no|y|n|[a-z0-9])\s*/i, "").trim();
          finalContent = serializeMessageContent({ choices: labels, explanations: explanation });
        }
      }

      onAnswerContentChange?.({
        type: ContentChangeEventType.NEW_ANSWER,
        questionId: pendingQuestion.id,
        content: finalContent,
      });
    } else {
      const isSingleChoice =
        questionType === QuestionTypeEnum.SINGLE_CHOICE ||
        questionType === QuestionTypeEnum.SINGLE_CHOICE_EXPLANATION;

      if (isSingleChoice) {
        onStoreQuestion?.({
          content: finalContent,
          question_type: questionType,
          choices: ["Yes", "No"],
          labelFormat: "none",
        });
      } else {
        const parsed = parseQuestionInput(finalContent);
        onStoreQuestion?.({
          content: parsed.content,
          question_type: questionType,
          choices: parsed.choices,
          labelFormat: parsed.labelFormat,
        });
      }
    }

    questionContent = "";
  };

  const handleVlmAction = async () => {
    if (!completionModel) return;

    isGenerating = true;
    if (isAnswering && pendingQuestion) {
      const text = await onGenerateAnswer?.({
        questionId: pendingQuestion.id,
        completionModel,
      });

      if (text) questionContent = text;
    } else {
      if (!onGenerateQuestion) {
        isGenerating = false;
        return;
      }
      const generated = await onGenerateQuestion(completionModel, questionType);

      if (generated) questionContent = generated.content;
    }
    isGenerating = false;
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (isAnswering && pendingQuestion && questionContent.trim() === "") {
      const pqType = pendingQuestion.data.question_type;
      const isSingleChoice =
        pqType === QuestionTypeEnum.SINGLE_CHOICE ||
        pqType === QuestionTypeEnum.SINGLE_CHOICE_EXPLANATION;

      if (isSingleChoice) {
        const key = e.key.toLowerCase();
        if (key === "y" || key === "n") {
          e.preventDefault();
          questionContent = key === "y" ? "Yes" : "No";
          handleSend();
          return;
        }
      }
    }

    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  let placeholder = $derived(
    isAnswering
      ? `Answering Question #${(pendingQuestion?.data.number ?? 0) + 1}...`
      : "Ask a question...",
  );
</script>

<div class="p-3 shrink-0">
  <div
    class={cn(
      "rounded-xl border transition-all overflow-hidden",
      isAnswering
        ? "bg-warning/5 border-warning/30 focus-within:border-warning/50 focus-within:ring-warning/5"
        : "bg-muted/30 border-border focus-within:border-primary/50 focus-within:ring-primary/5",
      "focus-within:bg-card focus-within:ring-4",
    )}
  >
    <AutoResizeTextarea
      {placeholder}
      bind:value={questionContent}
      onkeydown={handleKeyDown}
      class="w-full bg-transparent border-none focus:ring-0 py-3 px-4 text-sm text-foreground leading-relaxed placeholder:text-muted-foreground resize-none min-h-[44px] max-h-32"
    />

    <!-- Toolbar row -->
    <div class="flex items-center justify-between gap-2 px-2.5 pb-2.5">
      <div class="flex items-center gap-1.5">
        <!-- Question type badge -->
        {#if !isAnswering}
          <Select.Root
            type="single"
            value={questionType}
            items={questionTypeItems}
            open={isQuestionTypeOpen}
            onOpenChange={(open) => (isQuestionTypeOpen = open)}
            onValueChange={(value) => {
              if (value) questionType = value as QuestionTypeEnum;
            }}
          >
            <Select.Trigger aria-label="Question type" class={questionTypeChipClass}>
              {#snippet children()}
                <selectedTypeEntry.icon
                  weight="regular"
                  class={cn("h-3 w-3 shrink-0 text-muted-foreground transition-colors", {
                    "text-primary": isQuestionTypeOpen,
                  })}
                />
                <span class="truncate">{selectedTypeEntry.label}</span>
                <CaretDown
                  class={cn(
                    "h-3 w-3 shrink-0 text-muted-foreground transition-transform duration-200",
                    { "rotate-180": isQuestionTypeOpen },
                  )}
                />
              {/snippet}
            </Select.Trigger>

            <Select.Portal>
              <Select.Content
                sideOffset={10}
                class="z-50 min-w-[10rem] overflow-hidden rounded-2xl border border-border/50 bg-popover/96 p-1.5 text-popover-foreground shadow-[0_18px_48px_rgba(15,23,42,0.18)] backdrop-blur-md"
              >
                {#each questionTypes as qt}
                  {@const isSelected = questionType === qt.value}
                  <Select.Item
                    value={qt.value}
                    label={qt.label}
                    class="cursor-pointer rounded-xl px-3 py-2 outline-none transition-colors data-[highlighted]:bg-accent/80 data-[highlighted]:text-accent-foreground"
                  >
                    {#snippet children()}
                      <div class="flex items-center gap-3">
                        <div
                          class={cn(
                            "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border bg-background/70",
                            isSelected
                              ? "border-primary/25 text-primary"
                              : "border-border/35 text-muted-foreground/70",
                          )}
                        >
                          {#if isSelected}
                            <Check class="h-3 w-3" />
                          {:else}
                            <qt.icon weight="regular" class="h-3 w-3" />
                          {/if}
                        </div>
                        <span
                          class={cn("text-[13px] font-medium", {
                            "text-foreground font-semibold": isSelected,
                          })}
                        >
                          {qt.label}
                        </span>
                      </div>
                    {/snippet}
                  </Select.Item>
                {/each}
              </Select.Content>
            </Select.Portal>
          </Select.Root>
        {/if}

        <!-- Model badge -->
        <ModelSelectBadge
          models={vqaModels}
          selectedModelKey={selectedModel}
          disabled={!inferenceServer.connected || vqaModels.length === 0}
          label={vqaModelLabel}
          onValueChange={(key: string) => {
            selectedModel = key;
          }}
        />

        <!-- Settings button -->
        <IconButton
          tooltipContent="Model & Prompt Settings"
          disabled={completionModels.length === 0}
          onclick={() => (showPromptModal = !showPromptModal)}
          class="h-7 w-7"
        >
          <Gear weight="regular" size={14} />
        </IconButton>

        <!-- Debug prompt viewer -->
        <IconButton
          tooltipContent="View last VLM prompt"
          disabled={!lastVlmPromptStore.value}
          onclick={() => (showDebugModal = true)}
          class="h-7 w-7"
        >
          <Terminal weight="regular" size={14} />
        </IconButton>
      </div>

      <div class="flex items-center gap-1.5">
        <!-- VLM action -->
        <IconButton
          onclick={handleVlmAction}
          disabled={!completionModel || isGenerating}
          tooltipContent={isAnswering ? "Generate answer with VLM" : "Generate question from VLM"}
          class="h-7 w-7 bg-muted/60 text-muted-foreground hover:bg-accent border border-border/50"
        >
          <Sparkle weight="regular" size={16} />
        </IconButton>

        <!-- Send -->
        <IconButton
          onclick={handleSend}
          disabled={questionContent.trim() === ""}
          tooltipContent={isAnswering ? "Reply" : "Post"}
          class={cn(
            "h-7 w-7 text-primary-foreground shadow-sm",
            isAnswering ? "bg-warning hover:bg-warning/90" : "bg-primary hover:bg-primary/90",
          )}
        >
          <PaperPlaneRight weight="regular" size={16} />
        </IconButton>
      </div>
    </div>
  </div>
</div>

{#if showPromptModal}
  <ConfigurePromptModal
    {completionModels}
    {onCompletionModelsChange}
    onCancelPrompt={() => (showPromptModal = false)}
  />
{/if}

{#if showDebugModal && lastVlmPromptStore.value}
  <PromptDebugModal entry={lastVlmPromptStore.value} onClose={() => (showDebugModal = false)} />
{/if}

{#if isGenerating}
  <AiProcessingBadge
    overlay
    message={isAnswering ? "Generating answer..." : "Generating question..."}
  />
{/if}
