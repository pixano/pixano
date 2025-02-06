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
  import { answerChoicesToCheckboxsState, serializeMessageContent } from "../lib/utils";

  export let choices: string[];
  export let answer: Message | null;
  export let withExplanation: boolean;
  export let questionId: string;

  let explanation: string = (answer?.data.explanations as string[])[0] ?? "";
  let checked: boolean[] = answerChoicesToCheckboxsState((answer?.data.answers as string[]) ?? []);

  const answerId = answer?.id ?? null;

  const dispatch = createEventDispatcher();

  const handleCheckboxChange = (index: number, isChecked: boolean) => {
    checked[index] = isChecked;
    handleContentChange();
  };

  const handleContentChange = () => {
    const answers = checked.map((c, i) => (c ? i.toString() : null)).filter((c) => c !== null);
    const baseEventDetail = {
      content: serializeMessageContent({ choices: answers, explanation }),
      answers,
      explanations: [explanation],
    };

    const eventDetail: ContentChangeEvent = answerId
      ? { ...baseEventDetail, type: ContentChangeEventType.UPDATE, answerId }
      : {
          ...baseEventDetail,
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
      bind:value={explanation}
      on:blur={handleContentChange}
    />
  {/if}
</div>
