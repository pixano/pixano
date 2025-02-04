<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { Message } from "@pixano/core";
  import { MessageTypeEnum, QuestionTypeEnum } from "@pixano/core";
  import { isQuestionCompleted } from "../lib/utils";
  import MultipleChoiceAnswer from "./MultipleChoiceAnswer.svelte";
  import OpenAnswer from "./OpenAnswer.svelte";
  import QuestionContent from "./QuestionContent.svelte";
  import QuestionHeader from "./QuestionHeader.svelte";
  import SingleChoiceAnswer from "./SingleChoiceAnswer.svelte";

  export let messages: Message[];

  const question = messages.find((m) => m.data.type === MessageTypeEnum.QUESTION);

  if (question === undefined) {
    throw new Error("Question not found");
  }

  const answers = messages.filter((m) => m.data.type === MessageTypeEnum.ANSWER);
  $: questionCompleted = isQuestionCompleted(messages);

  const questionNumber = question.data.number + 1;

  const choices = question.data.choices as string[];
</script>

<div class="flex flex-col gap-2">
  <QuestionHeader {questionNumber} isQuestionCompleted={questionCompleted} />
  <QuestionContent content={question.data.content} />

  {#each answers as answer}
    {#if question.data.question_type === QuestionTypeEnum.OPEN}
      <OpenAnswer {answer} on:answerContentChange />
    {:else if question.data.question_type === QuestionTypeEnum.MULTI_CHOICE_EXPLANATION}
      <MultipleChoiceAnswer {answer} {choices} withExplanation={true} on:answerContentChange />
    {:else if question.data.question_type === QuestionTypeEnum.MULTI_CHOICE}
      <MultipleChoiceAnswer {answer} {choices} withExplanation={false} on:answerContentChange />
    {:else if question.data.question_type === QuestionTypeEnum.SINGLE_CHOICE_EXPLANATION}
      <SingleChoiceAnswer {answer} {choices} withExplanation={true} on:answerContentChange />
    {:else}
      <SingleChoiceAnswer {answer} {choices} withExplanation={false} on:answerContentChange />
    {/if}
  {/each}
</div>
