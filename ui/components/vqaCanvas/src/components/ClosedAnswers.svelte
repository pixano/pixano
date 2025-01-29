<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { QuestionTypeEnum } from "@pixano/core";
  import Checkbox from "@pixano/core/src/components/ui/checkbox/checkbox.svelte";

  export let choices: string[];
  export let questionType: QuestionTypeEnum;

  const withExplanation = questionType.includes("EXPLANATION");
</script>

<div class="p-2 border border-slate-100 rounded-lg flex flex-col gap-3">
  {#each choices as choice, index}
    <div class="flex flex-row gap-2 items-center">
      <Checkbox id={`choice-${index}`} name="choice" />
      <label id={`choice-${index}`}>{choice}</label>
    </div>
  {/each}
  {#if withExplanation}
    <input
      type="text"
      placeholder="Explanations"
      class="p-2 text-slate-800 placeholder-slate-500 outline-none border border-slate-100 rounded-lg"
    />
  {/if}
</div>
