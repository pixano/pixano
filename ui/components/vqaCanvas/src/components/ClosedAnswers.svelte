<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { Message, QuestionTypeEnum } from "@pixano/core";
  import Checkbox from "@pixano/core/src/components/ui/checkbox/checkbox.svelte";
  import { createEventDispatcher } from "svelte";
  import type { ContentChangeEvent } from "../lib/types";
  import { answerChoicesToCheckboxsState, serializeMessageContent } from "../lib/utils";

  export let choices: string[];
  export let questionType: QuestionTypeEnum;
  export let answer: Message;

  let explanation: string = (answer.data.explanations as string[])[0] ?? "";
  let checked: boolean[] = answerChoicesToCheckboxsState((answer.data.answers as string[]) ?? []);

  const withExplanation = questionType.includes("EXPLANATION");

  const dispatch = createEventDispatcher();

  const handleCheckboxChange = (index: number, isChecked: boolean) => {
    checked[index] = isChecked;
    handleContentChange();
  };

  const handleContentChange = () => {
    const newChoices = checked.map((c, i) => (c ? i.toString() : null)).filter((c) => c !== null);
    const newContent = serializeMessageContent({ choices: newChoices, explanation });

    const eventDetail: ContentChangeEvent = {
      answerId: answer.id,
      newContent,
      newChoices,
      explanation,
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
