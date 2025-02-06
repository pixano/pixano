<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { Message } from "@pixano/core";
  import { createEventDispatcher } from "svelte";
  import { ContentChangeEventType, type ContentChangeEvent } from "../lib/types";

  export let answer: Message | null;
  export let questionId: string;

  const answerId = answer?.id ?? null;

  const dispatch = createEventDispatcher();

  const handleBlur = (
    e: FocusEvent & {
      currentTarget: EventTarget & HTMLInputElement;
    },
  ) => {
    const baseEventDetail = {
      content: e.currentTarget.value,
      answers: undefined,
      explanations: undefined,
    };

    const eventDetail: ContentChangeEvent = answerId
      ? { ...baseEventDetail, type: ContentChangeEventType.UPDATE, answerId }
      : { ...baseEventDetail, type: ContentChangeEventType.NEW_ANSWER, questionId };

    dispatch("answerContentChange", eventDetail);
  };
</script>

<input
  type="text"
  value={answer?.data.content ?? ""}
  placeholder="Your answer here"
  class="p-2 text-slate-800 placeholder-slate-500 outline-none border border-slate-100 rounded-lg"
  on:blur={handleBlur}
/>
