<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { QuestionTypeEnum } from "@pixano/core";
  import Checkbox from "@pixano/core/src/components/ui/checkbox/checkbox.svelte";
  import { createEventDispatcher } from "svelte";
  import type { ContentChangeEvent } from "../lib/types";

  export let choices: string[];
  export let questionType: QuestionTypeEnum;
  export let answerId: string;

  let explanation: string = "";
  let checked: boolean[] = Array.from({ length: choices.length }).map(() => false);

  const withExplanation = questionType.includes("EXPLANATION");

  const dispatch = createEventDispatcher();

  const handleCheckboxChange = (index: number, isChecked: boolean) => {
    checked[index] = isChecked;
  };

  const handleContentChange = () => {
    const newChoices = checked.map((c, i) => (c ? i.toString() : null)).filter((c) => c !== null);
    const newContent = `[[${newChoices.join(",")}]] ${explanation}`;

    const eventDetail: ContentChangeEvent = { answerId, newContent, newChoices, explanation };
    dispatch("answerContentChange", eventDetail);
  };
</script>

<div class="p-2 border border-slate-100 rounded-lg flex flex-col gap-3">
  {#each choices as choice, index}
    <div class="flex flex-row gap-2 items-center">
      <Checkbox
        handleClick={(checked) => {
          handleCheckboxChange(index, checked);
          handleContentChange();
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
