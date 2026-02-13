<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import {
    CheckCircle2,
    Clock,
    ListOrdered,
    PencilLine,
    Save,
    Sparkles,
    Trash2,
    X,
  } from "lucide-svelte";
  import { createEventDispatcher } from "svelte";

  import type { Message } from "@pixano/core";
  import { MessageTypeEnum, QuestionTypeEnum } from "@pixano/core";

  import { completionModelsStore } from "../../../stores/completionModels";
  import type { LabelFormat } from "../../addQuestion/types/StoreQuestionEvent";
  import { ContentChangeEventType } from "../types";
  import { deserializeMessageContent, isQuestionCompleted } from "../utils";

  export let messages: Message[];

  const dispatch = createEventDispatcher();

  const question = messages.find((m) => m.data.type === MessageTypeEnum.QUESTION);

  if (question === undefined) {
    throw new Error("Question not found");
  }

  $: questionType = question.data.question_type as QuestionTypeEnum;
  $: questionNumber = question.data.number + 1;
  $: choices = question.data.choices as string[];

  $: answers = messages.filter((m) => m.data.type === MessageTypeEnum.ANSWER);
  $: questionCompleted = isQuestionCompleted(messages);

  let editingId: string | null = null;
  let editContent = "";

  const startEditing = (m: Message) => {
    editingId = m.id;
    editContent = m.data.content;
  };

  const cancelEditing = () => {
    editingId = null;
  };

  const saveEdit = (m: Message) => {
    dispatch("answerContentChange", {
      type: ContentChangeEventType.UPDATE,
      answerId: m.id,
      content: editContent,
    });
    editingId = null;
  };

  const handleGenerateAnswer = () => {
    const completionModel =
      $completionModelsStore.filter((model) => model.selected)[0]?.name ?? undefined;
    if (completionModel === undefined) {
      console.error("ERROR: No model selected");
      return;
    }

    dispatch("generateAnswer", {
      questionId: question.id,
      completionModel,
    });
  };

  // Determine label format from UI metadata (or default to none for single choice, alpha_upper otherwise)
  $: labelFormat =
    ((question.ui as Record<string, unknown>)?.labelFormat as LabelFormat | undefined) ??
    (isSingleChoice ? "none" : "alpha_upper");

  const getChoiceLabel = (index: number, format: LabelFormat | undefined): string => {
    switch (format) {
      case "numeric":
        return String(index + 1);
      case "alpha_lower":
        return String.fromCharCode(97 + index);
      case "none":
        return "";
      case "alpha_upper":
      default:
        return String.fromCharCode(65 + index);
    }
  };

  $: isSingleChoice =
    questionType === QuestionTypeEnum.SINGLE_CHOICE ||
    questionType === QuestionTypeEnum.SINGLE_CHOICE_EXPLANATION;
  $: isMultiChoice =
    questionType === QuestionTypeEnum.MULTI_CHOICE ||
    questionType === QuestionTypeEnum.MULTI_CHOICE_EXPLANATION;
  $: isOpen = questionType === QuestionTypeEnum.OPEN;

  const getAnswerDisplay = (answer: Message): { selection: string; explanation: string } => {
    if (isOpen) {
      return { selection: answer.data.content, explanation: "" };
    }
    const { checked, explanations } = deserializeMessageContent(answer.data.content ?? null);
    const selected = checked
      .map((isChecked: boolean, i: number) => {
        if (!isChecked || i >= choices.length) return null;
        const label = getChoiceLabel(i, labelFormat);
        return label ? `${label}. ${choices[i]}` : choices[i];
      })
      .filter((c): c is string => c !== null);
    return { selection: selected.join(", "), explanation: explanations };
  };

  let confirmingDelete = false;

  const handleDelete = () => {
    dispatch("deleteQuestion", { questionId: question.id });
    confirmingDelete = false;
  };
</script>

<div class="relative pl-8 group/thread">
  <!-- Visual Link (Vertical Line) -->
  <div
    class="absolute left-3.5 top-2 bottom-2 w-0.5 bg-border group-hover/thread:bg-primary/20 transition-colors"
  ></div>

  <div class="flex flex-col gap-6">
    <!-- Question bubble -->
    <div class="relative flex flex-col gap-1 items-start max-w-[90%] self-start">
      <!-- Node on the line -->
      <div
        class="absolute -left-[25px] top-3.5 w-3 h-3 rounded-full border-2 border-border bg-card z-10 {questionCompleted
          ? 'border-green-500'
          : 'border-warning'}"
      ></div>

      <div
        class="flex items-center gap-2 px-1 text-[10px] uppercase tracking-widest font-bold text-muted-foreground"
      >
        <span>Question #{questionNumber}</span>
        {#if isOpen}
          <span
            class="px-1.5 py-0.5 rounded bg-muted text-muted-foreground text-[9px] tracking-tight normal-case font-semibold"
          >
            Open question
          </span>
        {:else if isSingleChoice}
          <span
            class="px-1.5 py-0.5 rounded bg-info/10 text-info text-[9px] tracking-tight normal-case font-semibold"
          >
            Yes / No
          </span>
        {:else if isMultiChoice}
          <span
            class="px-1.5 py-0.5 rounded bg-primary/10 text-primary text-[9px] tracking-tight normal-case font-semibold"
          >
            Multiple choice
          </span>
        {/if}
        {#if questionCompleted}
          <CheckCircle2 size={12} class="text-success" />
        {:else}
          <Clock size={12} class="text-warning animate-pulse" />
        {/if}
      </div>

      <div
        class="relative bg-card border border-border rounded-2xl rounded-tl-none px-5 py-4 shadow-sm text-sm text-foreground leading-relaxed group/bubble transition-all hover:border-border"
      >
        {#if editingId === question.id}
          <div class="flex flex-col gap-2 min-w-[240px]">
            <textarea
              bind:value={editContent}
              class="w-full text-sm border-none focus:ring-0 p-0 resize-none bg-muted/30 rounded"
              rows="3"
            ></textarea>
            <div class="flex justify-end gap-1">
              <button on:click={cancelEditing} class="p-1 text-muted-foreground hover:text-foreground">
                <X size={14} />
              </button>
              <button
                on:click={() => saveEdit(question)}
                class="p-1 text-primary hover:text-primary-dark"
              >
                <Save size={14} />
              </button>
            </div>
          </div>
        {:else}
          <div class="space-y-3">
            <p class="font-medium text-foreground">{question.data.content}</p>

            {#if choices && choices.length > 0 && !isSingleChoice}
              <div class="pt-2 border-t border-border/50 space-y-1.5">
                <div
                  class="flex items-center gap-1.5 text-[10px] font-bold text-muted-foreground uppercase tracking-tight mb-1"
                >
                  <ListOrdered size={12} /> Options
                </div>
                {#each choices as choice, i}
                  {@const label = getChoiceLabel(i, labelFormat)}
                  <div class="flex gap-2 items-start text-xs text-muted-foreground">
                    {#if label}
                      <span
                        class="flex-none w-5 h-5 rounded bg-muted flex items-center justify-center font-bold text-muted-foreground"
                      >
                        {label}
                      </span>
                    {/if}
                    <span class="pt-0.5">{choice}</span>
                  </div>
                {/each}
              </div>
            {/if}
          </div>

          <div
            class="absolute -right-[60px] top-0 flex flex-col gap-0.5 opacity-0 group-hover/bubble:opacity-100 transition-all"
          >
            <button
              on:click={() => startEditing(question)}
              class="p-1.5 text-muted-foreground/50 hover:text-primary transition-colors"
              title="Edit question"
            >
              <PencilLine size={14} />
            </button>
            <button
              on:click={() => {
                confirmingDelete = true;
              }}
              class="p-1.5 text-muted-foreground/50 hover:text-destructive transition-colors"
              title="Delete question"
            >
              <Trash2 size={14} />
            </button>
          </div>

          {#if confirmingDelete}
            <div
              class="mt-2 p-2 bg-destructive/10 border border-destructive/20 rounded-lg text-xs text-destructive flex items-center justify-between gap-2"
            >
              <span>Delete this question and its answers?</span>
              <div class="flex gap-1 shrink-0">
                <button
                  on:click={() => {
                    confirmingDelete = false;
                  }}
                  class="px-2 py-0.5 rounded text-muted-foreground hover:bg-card transition-colors"
                >
                  Cancel
                </button>
                <button
                  on:click={handleDelete}
                  class="px-2 py-0.5 rounded bg-destructive text-destructive-foreground hover:bg-destructive/90 transition-colors"
                >
                  Delete
                </button>
              </div>
            </div>
          {/if}
        {/if}
      </div>
    </div>

    <!-- Answer bubble(s) -->
    <div class="flex flex-col gap-4 items-start w-full">
      {#each answers as answer}
        <div class="relative flex flex-col items-start gap-1 max-w-[95%] w-full group/bubble">
          <!-- Node on the line -->
          <div class="absolute -left-[25px] top-3.5 w-2 h-2 rounded-full bg-primary/30 z-10"></div>

          <div class="px-1 text-[10px] uppercase tracking-widest font-bold text-muted-foreground">
            Answer
          </div>
          <div
            class="relative bg-primary/5 border border-primary/20 rounded-2xl rounded-tl-none px-5 py-4 shadow-sm w-full transition-all hover:border-primary/40"
          >
            {#if editingId === answer.id}
              <div class="flex flex-col gap-2">
                <textarea
                  bind:value={editContent}
                  class="w-full text-sm border-none focus:ring-0 p-0 resize-none bg-card/50 rounded"
                  rows="3"
                ></textarea>
                <div class="flex justify-end gap-1">
                  <button on:click={cancelEditing} class="p-1 text-muted-foreground hover:text-foreground">
                    <X size={14} />
                  </button>
                  <button
                    on:click={() => saveEdit(answer)}
                    class="p-1 text-primary hover:text-primary-dark"
                  >
                    <Save size={14} />
                  </button>
                </div>
              </div>
            {:else}
              {@const display = getAnswerDisplay(answer)}
              <div class="text-sm text-foreground leading-relaxed">
                {#if display.selection}
                  <p class="font-medium">{display.selection}</p>
                {/if}
                {#if display.explanation}
                  <p class="text-muted-foreground italic {display.selection ? 'mt-1' : ''}">
                    {display.explanation}
                  </p>
                {/if}
              </div>
              <button
                on:click={() => startEditing(answer)}
                class="absolute -right-8 top-0 p-1.5 text-muted-foreground/50 hover:text-primary opacity-0 group-hover/bubble:opacity-100 transition-all"
                title="Edit answer"
              >
                <PencilLine size={14} />
              </button>
            {/if}
          </div>
        </div>
      {/each}

      {#if answers.length === 0}
        <div class="relative flex flex-col items-start gap-2 w-full">
          <!-- Node on the line (placeholder) -->
          <div
            class="absolute -left-[25px] top-3.5 w-2 h-2 rounded-full bg-muted border border-border z-10"
          ></div>

          <button
            class="ml-1 flex items-center gap-2 px-3 py-1.5 bg-card border border-border rounded-lg text-[11px] font-bold uppercase tracking-tighter text-muted-foreground hover:border-primary hover:text-primary transition-all group/btn shadow-sm"
            on:click={handleGenerateAnswer}
          >
            <Sparkles size={12} class="group-hover/btn:animate-pulse" />
            VLM Suggestion
          </button>
        </div>
      {/if}
    </div>
  </div>
</div>
