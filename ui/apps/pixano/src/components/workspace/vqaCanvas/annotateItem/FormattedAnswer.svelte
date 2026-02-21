<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<!-- When svelte is updated, this component can be replaced by a {#snnipet} in QuestionForm.svelte -->

<script lang="ts">
  import { Message, QuestionTypeEnum } from "$lib/types/dataset";
  import type { ContentChangeEvent } from "$lib/types/vqa";

  import MultipleChoiceAnswer from "./MultipleChoiceAnswer.svelte";
  import OpenAnswer from "./OpenAnswer.svelte";
  import SingleChoiceAnswer from "./SingleChoiceAnswer.svelte";

  interface Props {
    questionId: string;
    questionType: QuestionTypeEnum;
    answer: Message | null;
    choices: string[];
    disabled?: boolean;
    onAnswerContentChange?: (event: ContentChangeEvent) => void;
  }

  let {
    questionId,
    questionType,
    answer,
    choices,
    disabled = false,
    onAnswerContentChange,
  }: Props = $props();
</script>

{#if questionType === QuestionTypeEnum.OPEN}
  <OpenAnswer {questionId} {answer} {disabled} {onAnswerContentChange} />
{:else if questionType === QuestionTypeEnum.MULTI_CHOICE_EXPLANATION}
  <MultipleChoiceAnswer
    {questionId}
    {answer}
    {choices}
    {disabled}
    withExplanation={true}
    {onAnswerContentChange}
  />
{:else if questionType === QuestionTypeEnum.MULTI_CHOICE}
  <MultipleChoiceAnswer
    {questionId}
    {answer}
    {choices}
    {disabled}
    withExplanation={false}
    {onAnswerContentChange}
  />
{:else if questionType === QuestionTypeEnum.SINGLE_CHOICE_EXPLANATION}
  <SingleChoiceAnswer
    {questionId}
    {answer}
    {choices}
    {disabled}
    withExplanation={true}
    {onAnswerContentChange}
  />
{:else}
  <SingleChoiceAnswer
    {questionId}
    {answer}
    {choices}
    {disabled}
    withExplanation={false}
    {onAnswerContentChange}
  />
{/if}
