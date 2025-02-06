<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<!-- When svelte is updated, this component could be replaced by a {#snnipet} in QuestionForm.svelte -->

<script lang="ts">
  import { Message, QuestionTypeEnum } from "@pixano/core";
  import MultipleChoiceAnswer from "./MultipleChoiceAnswer.svelte";
  import OpenAnswer from "./OpenAnswer.svelte";
  import SingleChoiceAnswer from "./SingleChoiceAnswer.svelte";

  export let questionId: string;
  export let questionType: QuestionTypeEnum;
  export let answer: Message | null;
  export let choices: string[];
</script>

{#if questionType === QuestionTypeEnum.OPEN}
  <OpenAnswer {questionId} {answer} on:answerContentChange />
{:else if questionType === QuestionTypeEnum.MULTI_CHOICE_EXPLANATION}
  <MultipleChoiceAnswer
    {questionId}
    {answer}
    {choices}
    withExplanation={true}
    on:answerContentChange
  />
{:else if questionType === QuestionTypeEnum.MULTI_CHOICE}
  <MultipleChoiceAnswer
    {questionId}
    {answer}
    {choices}
    withExplanation={false}
    on:answerContentChange
  />
{:else if questionType === QuestionTypeEnum.SINGLE_CHOICE_EXPLANATION}
  <SingleChoiceAnswer
    {questionId}
    {answer}
    {choices}
    withExplanation={true}
    on:answerContentChange
  />
{:else}
  <SingleChoiceAnswer
    {questionId}
    {answer}
    {choices}
    withExplanation={false}
    on:answerContentChange
  />
{/if}
