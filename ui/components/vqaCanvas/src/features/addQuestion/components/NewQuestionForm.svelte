<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { createEventDispatcher } from "svelte";

  import { QuestionTypeEnum } from "@pixano/core";
  import { AutoResizeTextarea } from "@pixano/core/src/components/ui/autoresize-textarea";
  import PrimaryButton from "@pixano/core/src/components/ui/molecules/PrimaryButton.svelte";

  import type { StoreQuestionEvent } from "../types";
  import AddChoiceButton from "./AddChoiceButton.svelte";
  import QuestionChoice from "./NewQuestionChoice.svelte";

  export let questionType: QuestionTypeEnum;
  export let questionChoices: string[];
  export let questionContent: string;

  const dispatch = createEventDispatcher();

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
  <AutoResizeTextarea placeholder="What is the main object ?" bind:value={questionContent} />

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
