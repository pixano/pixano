<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { Message } from "@pixano/core";
  import { MessageTypeEnum, QuestionTypeEnum } from "@pixano/core";
  import { isQuestionCompleted } from "../lib/utils";
  import FormattedAnswer from "./FormattedAnswer.svelte";
  import QuestionContent from "./QuestionContent.svelte";
  import QuestionHeader from "./QuestionHeader.svelte";

  export let messages: Message[];

  const question = messages.find((m) => m.data.type === MessageTypeEnum.QUESTION);

  if (question === undefined) {
    throw new Error("Question not found");
  }

  const questionType = question.data.question_type as QuestionTypeEnum;
  const questionNumber = question.data.number + 1;
  const choices = question.data.choices as string[];

  $: answers = messages.filter((m) => m.data.type === MessageTypeEnum.ANSWER);
  $: questionCompleted = isQuestionCompleted(messages);
</script>

<div class="flex flex-col gap-2">
  <QuestionHeader {questionNumber} isQuestionCompleted={questionCompleted} />
  <QuestionContent content={question.data.content} />

  {#each answers as answer}
    <FormattedAnswer
      questionId={question.id}
      {questionType}
      {answer}
      {choices}
      on:answerContentChange
    />
  {/each}

  {#if answers.length === 0}
    <FormattedAnswer
      questionId={question.id}
      {questionType}
      answer={null}
      {choices}
      on:answerContentChange
    />
  {/if}
</div>
