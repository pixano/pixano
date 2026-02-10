<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { createEventDispatcher } from "svelte";

  import type { Message } from "@pixano/core";
  import Checkbox from "@pixano/core/src/components/ui/checkbox/checkbox.svelte";

  import { ContentChangeEventType, type ContentChangeEvent } from "../types";
  import {
    checkboxsStateToAnswerChoices,
    deserializeMessageContent,
    serializeMessageContent,
  } from "../utils";

  export let choices: string[];
  export let answer: Message | null;
  export let withExplanation: boolean;
  export let questionId: string;
  export let disabled = false;

  let { checked, explanations } = deserializeMessageContent(answer?.data.content ?? null);

  const answerId = answer?.id ?? null;

  const dispatch = createEventDispatcher();

  const handleCheckboxChange = (index: number, isChecked: boolean) => {
    if (disabled) return;
    checked[index] = isChecked;
    handleContentChange();
  };

  const handleContentChange = () => {
    if (disabled) return;
    const selectedChoices = checkboxsStateToAnswerChoices(checked);
    const content = serializeMessageContent({ choices: selectedChoices, explanations });

    const eventDetail: ContentChangeEvent = answerId
      ? { content, type: ContentChangeEventType.UPDATE, answerId }
      : {
          content,
          type: ContentChangeEventType.NEW_ANSWER,
          questionId,
        };

    dispatch("answerContentChange", eventDetail);
  };
</script>

<div class="flex flex-col gap-3 {disabled ? 'pointer-events-none opacity-70' : ''}">
  {#each choices as choice, index}
    <div class="flex flex-row gap-2 items-center">
      <!-- Do not bind with checked variable because handleClick is triggered before the change applies to binded value -->
      <Checkbox
        {disabled}
        checked={checked[index]}
        handleClick={(checked) => {
          handleCheckboxChange(index, checked);
        }}
      />
      <span class="text-sm text-slate-700">{choice}</span>
    </div>
  {/each}
  {#if withExplanation}
    <div class="mt-2 pt-2 border-t border-primary/10">
      <input
        type="text"
        placeholder="Provide an explanation..."
        class="w-full bg-transparent p-0 text-sm text-slate-700 outline-none placeholder:text-slate-300 italic {disabled ? 'cursor-default' : ''}"
        bind:value={explanations}
        on:blur={handleContentChange}
        {disabled}
      />
    </div>
  {/if}
</div>
