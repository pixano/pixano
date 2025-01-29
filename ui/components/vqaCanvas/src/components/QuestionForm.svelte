<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { Message } from "@pixano/core";
  import { MessageTypeEnum, QuestionTypeEnum } from "@pixano/core";
  import OpenAnswer from "./OpenAnswer.svelte";
  import ClosedAnswers from "./ClosedAnswers.svelte";
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
</script>

<div class="flex flex-col gap-2">
  <QuestionHeader {questionNumber} {isQuestionCompleted} />
  <QuestionContent content={question.data.content} />

  {#if question.data.question_type === QuestionTypeEnum.OPEN}
    {#each answers as answer}
      <OpenAnswer {answer} />
    {/each}
  {:else}
    <ClosedAnswers choices={question.data.choices} questionType={question.data.question_type} />
  {/if}
</div>
