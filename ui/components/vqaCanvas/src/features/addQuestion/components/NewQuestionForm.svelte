<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { createEventDispatcher, tick } from "svelte";

  import { QuestionTypeEnum } from "@pixano/core";
  import PrimaryButton from "@pixano/core/src/components/ui/molecules/PrimaryButton.svelte";

  import type { StoreQuestionEvent } from "../types";
  import AddChoiceButton from "./AddChoiceButton.svelte";
  import QuestionChoice from "./NewQuestionChoice.svelte";

  export let questionType: QuestionTypeEnum;
  export let questionChoices: string[];
  export let questionContent: string;

  const dispatch = createEventDispatcher();

  let textarea: HTMLTextAreaElement | null = null;

  $: if (questionContent) {
    void adjustHeight();
  }

  const adjustHeight = async () => {
    if (textarea) {
      textarea.style.height = "auto";
      await tick();
      textarea.style.height = textarea.scrollHeight + "px";
    }
  };

  const handleStoreQuestion = () => {
    const eventDetail: StoreQuestionEvent = {
      content: questionContent,
      question_type: questionType,
      choices: questionChoices,
    };
    dispatch("storeQuestion", eventDetail);
  };
</script>

<div class="px-3 flex flex-col gap-2">
  <h5 class="font-medium">Question</h5>
  <textarea
    placeholder="What is the main object ?"
    class="p-2 border rounded-lg border-gray-200 outline-none text-slate-800 focus:border-primary resize-none overflow-hidden"
    bind:this={textarea}
    bind:value={questionContent}
  />

  {#if questionType !== QuestionTypeEnum.OPEN}
    <div class="flex flex-col gap-2">
      <!-- eslint-disable-next-line @typescript-eslint/no-unused-vars -->
      {#each questionChoices as _, index}
        <QuestionChoice {index} bind:questionChoices />
      {/each}

      <AddChoiceButton bind:questionChoices />
    </div>
  {/if}

  <PrimaryButton isSelected disabled={questionContent === ""} on:click={handleStoreQuestion}>
    Confirm changes
  </PrimaryButton>
</div>
