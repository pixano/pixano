<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { Message } from "@pixano/core";
  import { MessageTypeEnum, QuestionTypeEnum } from "@pixano/core";
  import ClosedAnswers from "./ClosedAnswers.svelte";
  import OpenAnswer from "./OpenAnswer.svelte";
  import QuestionContent from "./QuestionContent.svelte";
  import QuestionHeader from "./QuestionHeader.svelte";

  export let messages: Message[];

  const question = messages.find((m) => m.data.type === MessageTypeEnum.QUESTION);
  const answers = messages.filter((m) => m.data.type === MessageTypeEnum.ANSWER);

  if (question === undefined) {
    throw new Error("Question not found");
  }

  const isQuestionCompleted = answers.every((a) => a.data.content);
  const questionNumber = question.data.number + 1;

  const choices = question.data.choices as string[];
  const questionType = question.data.question_type as QuestionTypeEnum;
</script>

<div class="flex flex-col gap-2">
  <QuestionHeader {questionNumber} {isQuestionCompleted} />
  <QuestionContent content={question.data.content} />

  {#each answers as answer}
    {#if question.data.question_type === QuestionTypeEnum.OPEN}
      <OpenAnswer {answer} on:answerContentChange />
    {:else}
      <ClosedAnswers answerId={answer.id} {choices} {questionType} on:answerContentChange />
    {/if}
  {/each}
</div>
