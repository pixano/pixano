<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import {
    CheckCircle2,
    HelpCircle,
    ListOrdered,
    MessageSquare,
    Reply,
    Send,
    Sparkles,
  } from "lucide-svelte";
  import { createEventDispatcher } from "svelte";

  import {
    AutoResizeTextarea,
    IconButton,
    LoadingModal,
    QuestionTypeEnum,
    type Message,
  } from "@pixano/core";

  import { generateQuestion } from "../../../../../datasetItemWorkspace/src/lib/stores/mutations/generateQuestion";
  import { completionModelsStore } from "../../../stores/completionModels";
  import type { LabelFormat } from "../../addQuestion/types/StoreQuestionEvent";
  import { ContentChangeEventType } from "../types";
  import { serializeMessageContent } from "../utils/serializeMessageContent";

  export let pendingQuestion: Message | null = null;

  const dispatch = createEventDispatcher();
  let questionContent = "";
  let questionType = QuestionTypeEnum.OPEN;
  let isGenerating = false;

  $: completionModel = $completionModelsStore.find((m) => m.selected)?.name;
  $: isAnswering = !!pendingQuestion;

  const allowedTypes = [
    { type: QuestionTypeEnum.OPEN, label: "Open Question", icon: MessageSquare },
    { type: QuestionTypeEnum.SINGLE_CHOICE, label: "Single Choice", icon: CheckCircle2 },
    { type: QuestionTypeEnum.MULTI_CHOICE, label: "Multiple Choice", icon: ListOrdered },
  ];

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

    // Detect label format from first choice line
    const firstLine = potentialChoices[0];
    let labelFormat: LabelFormat = "none";
    if (numericRegex.test(firstLine)) labelFormat = "numeric";
    else if (alphaLowerRegex.test(firstLine)) labelFormat = "alpha_lower";
    else if (alphaUpperRegex.test(firstLine)) labelFormat = "alpha_upper";
    else if (bulletRegex.test(firstLine)) labelFormat = "none";

    // Strip labels from all choice lines
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

        // 1. Check for Yes/No shortcuts if applicable
        if (isSingleChoice) {
          if (
            lowerContent === "y" ||
            lowerContent === "yes" ||
            lowerContent.startsWith("y ") ||
            lowerContent.startsWith("yes ")
          ) {
            selectedIndices = [0]; // Yes
          } else if (
            lowerContent === "n" ||
            lowerContent === "no" ||
            lowerContent.startsWith("n ") ||
            lowerContent.startsWith("no ")
          ) {
            selectedIndices = [1]; // No
          }
        }

        // 2. Check for label shortcuts (1, 2, a, b, etc.) if no Yes/No match
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
              if (isSingleChoice) break; // Only take first for single choice
            } else {
              // If any part doesn't match a label, we might want to treat the whole thing as text
              // But let's be flexible: if it's just one part and it didn't match, it's text.
              // If it's multiple parts, some matching labels and some not, it's ambiguous.
            }
          }

          if (candidateIndices.length > 0) {
            selectedIndices = candidateIndices;
          }
        }

        // 3. Serialize if matches were found
        if (selectedIndices.length > 0) {
          const labels = selectedIndices.map((i) => String.fromCharCode(i + 65));
          const explanation = content.replace(/^(yes|no|y|n|[a-z0-9])\s*/i, "").trim();
          finalContent = serializeMessageContent({ choices: labels, explanations: explanation });
        }
      }

      dispatch("answerContentChange", {
        type: ContentChangeEventType.NEW_ANSWER,
        questionId: pendingQuestion.id,
        content: finalContent,
      });
    } else {
      const isSingleChoice =
        questionType === QuestionTypeEnum.SINGLE_CHOICE ||
        questionType === QuestionTypeEnum.SINGLE_CHOICE_EXPLANATION;

      if (isSingleChoice) {
        // Yes/No is implicit for single choice — no parsing needed
        dispatch("storeQuestion", {
          content: finalContent,
          question_type: questionType,
          choices: ["Yes", "No"],
          labelFormat: "none",
        });
      } else {
        const parsed = parseQuestionInput(finalContent);
        dispatch("storeQuestion", {
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

    if (isAnswering && pendingQuestion) {
      dispatch("generateAnswer", {
        questionId: pendingQuestion.id,
        completionModel,
      });
    } else {
      isGenerating = true;
      const generated: { content: string; choices: string[] } | null =
        await generateQuestion(completionModel);
      isGenerating = false;

      if (generated) {
        dispatch("storeQuestion", {
          content: generated.content,
          question_type: QuestionTypeEnum.OPEN,
          choices: generated.choices || [],
        });
      }
    }
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
</script>

<div
  class="p-4 bg-white border-t border-border space-y-3 shadow-[0_-4px_10px_rgba(0,0,0,0.03)] shrink-0"
>
  <!-- Dynamic Status Label -->
  <div class="flex items-center justify-between">
    <div class="flex items-center gap-2">
      <div
        class="flex items-center gap-1.5 px-2 py-0.5 rounded-md {isAnswering
          ? 'bg-amber-50 text-amber-600'
          : 'bg-primary/5 text-primary'} text-[10px] font-bold uppercase tracking-widest border {isAnswering
          ? 'border-amber-100'
          : 'border-primary/10'}"
      >
        {#if isAnswering}
          <Reply size={10} /> Answering Question #{(pendingQuestion?.data.number ?? 0) + 1}
        {:else}
          <MessageSquare size={10} /> New Question
        {/if}
      </div>
    </div>
  </div>

  <div
    class="w-full relative {isAnswering
      ? 'bg-amber-50/30'
      : 'bg-slate-50'} rounded-xl border {isAnswering
      ? 'border-amber-200 focus-within:border-amber-400 focus-within:ring-amber-400/5'
      : 'border-slate-200 focus-within:border-primary/50 focus-within:ring-primary/5'} focus-within:bg-white focus-within:ring-4 transition-all overflow-hidden"
  >
    <AutoResizeTextarea
      placeholder={isAnswering ? "Provide the answer..." : "Ask a question..."}
      bind:value={questionContent}
      on:keydown={handleKeyDown}
      class="w-full bg-transparent border-none focus:ring-0 py-3 px-4 text-sm text-slate-700 leading-relaxed placeholder:text-slate-400 resize-none min-h-[44px] max-h-32"
    />
  </div>

  <div class="flex items-center justify-between gap-3">
    <div class="flex items-center gap-1 bg-slate-100/50 p-1 rounded-xl border border-slate-200/50">
      {#if !isAnswering}
        {#each allowedTypes as item}
          <IconButton
            selected={questionType === item.type}
            on:click={() => (questionType = item.type)}
            tooltipContent={item.label}
            class="h-8 w-8"
          >
            <svelte:component this={item.icon} size={14} />
          </IconButton>
        {/each}
      {/if}
    </div>

    <div class="flex items-center gap-2">
      <IconButton
        on:click={handleVlmAction}
        disabled={!completionModel || isGenerating}
        tooltipContent={isAnswering ? "Generate answer with VLM" : "Generate question from VLM"}
        class="h-10 w-10 bg-slate-100 text-slate-600 hover:bg-slate-200 border border-slate-200"
      >
        <Sparkles size={18} />
      </IconButton>

      <IconButton
        on:click={handleSend}
        disabled={questionContent.trim() === ""}
        tooltipContent={isAnswering ? "Reply" : "Post"}
        class="h-10 w-10 {isAnswering
          ? 'bg-amber-500 hover:bg-amber-600'
          : 'bg-primary hover:bg-primary/90'} text-white shadow-md"
      >
        <Send size={18} />
      </IconButton>
    </div>
  </div>

  <p class="text-[10px] text-slate-400 flex items-center gap-1 px-1">
    <HelpCircle size={10} />
    {#if isAnswering}
      Complete this question by providing an answer manually or using <strong>VLM</strong>
      .
    {:else}
      Type a question or use <strong>VLM</strong>
      to suggest one.
    {/if}
  </p>
</div>

{#if isGenerating}
  <LoadingModal />
{/if}
