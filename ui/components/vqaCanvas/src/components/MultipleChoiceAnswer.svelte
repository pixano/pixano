<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { Message } from "@pixano/core";
  import Checkbox from "@pixano/core/src/components/ui/checkbox/checkbox.svelte";
  import { createEventDispatcher } from "svelte";
  import { ContentChangeEventType, type ContentChangeEvent } from "../lib/types";
  import {
    checkboxsStateToAnswerChoices,
    deserializeMessageContent,
    serializeMessageContent,
  } from "../lib/utils";

  export let choices: string[];
  export let answer: Message | null;
  export let withExplanation: boolean;
  export let questionId: string;

  let { checked, explanations } = deserializeMessageContent(answer?.data.content ?? null);

  const answerId = answer?.id ?? null;

  const dispatch = createEventDispatcher();

  const handleCheckboxChange = (index: number, isChecked: boolean) => {
    checked[index] = isChecked;
    handleContentChange();
  };

  const handleContentChange = () => {
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

<div class="p-2 border border-slate-100 rounded-lg flex flex-col gap-3">
  {#each choices as choice, index}
    <div class="flex flex-row gap-2 items-center">
      <!-- Do not bind with checked variable because handleClick is triggered before the change applies to binded value -->
      <Checkbox
        checked={checked[index]}
        handleClick={(checked) => {
          handleCheckboxChange(index, checked);
        }}
      />
      <span>{choice}</span>
    </div>
  {/each}
  {#if withExplanation}
    <input
      type="text"
      placeholder="Explanations"
      class="p-2 text-slate-800 placeholder-slate-500 outline-none border border-slate-100 rounded-lg"
      bind:value={explanations}
      on:blur={handleContentChange}
    />
  {/if}
</div>
