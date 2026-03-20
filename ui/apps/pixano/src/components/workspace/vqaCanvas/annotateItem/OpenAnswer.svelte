<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { Message } from "$lib/types/dataset";
  import { ContentChangeEventType, type ContentChangeEvent } from "$lib/types/vqa";
  import { AutoResizeTextarea } from "$lib/ui";

  interface Props {
    answer: Message | null;
    questionId: string;
    disabled?: boolean;
    onAnswerContentChange?: (event: ContentChangeEvent) => void;
  }

  let { answer, questionId, disabled = false, onAnswerContentChange }: Props = $props();

  let answerContent = $state("");

  $effect(() => {
    answerContent = answer?.data.content ?? "";
  });

  const validateChange = () => {
    const messageId = answer?.id ?? null;
    const eventDetail: ContentChangeEvent = messageId
      ? { content: answerContent, type: ContentChangeEventType.UPDATE, messageId }
      : { content: answerContent, type: ContentChangeEventType.NEW_ANSWER, questionId };

    onAnswerContentChange?.(eventDetail);
  };
</script>

<AutoResizeTextarea
  placeholder="Type the answer here..."
  bind:value={answerContent}
  onblur={validateChange}
  {disabled}
  class="w-full bg-transparent border-none focus:ring-0 p-0 text-sm text-slate-700 leading-relaxed placeholder:text-slate-300 {disabled
    ? 'cursor-default'
    : ''}"
/>
