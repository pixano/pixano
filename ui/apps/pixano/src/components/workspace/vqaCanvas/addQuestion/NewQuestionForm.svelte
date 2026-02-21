<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { QuestionTypeEnum } from "$lib/types/dataset";
  import { AutoResizeTextarea, PrimaryButton } from "$lib/ui";

  import type { StoreQuestionEvent } from "$lib/types/vqa";
  import AddChoiceButton from "./AddChoiceButton.svelte";
  import QuestionChoice from "./NewQuestionChoice.svelte";

  interface Props {
    questionType: QuestionTypeEnum;
    questionChoices: string[];
    questionContent: string;
    onStoreQuestion?: (event: StoreQuestionEvent) => void;
  }

  let {
    questionType,
    questionChoices = $bindable(),
    questionContent = $bindable(),
    onStoreQuestion,
  }: Props = $props();

  const handleStoreQuestion = () => {
    const eventDetail: StoreQuestionEvent = {
      content: questionContent,
      question_type: questionType,
      choices: questionChoices,
    };
    onStoreQuestion?.(eventDetail);
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

  <PrimaryButton isSelected disabled={questionContent === ""} onclick={handleStoreQuestion}>
    Confirm changes
  </PrimaryButton>
</div>
