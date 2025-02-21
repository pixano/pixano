<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { createEventDispatcher } from "svelte";

  import type { Message } from "@pixano/core";
  import { RadioGroup } from "@pixano/core";

  import { ContentChangeEventType, type ContentChangeEvent } from "../types";
  import { deserializeMessageContent, serializeMessageContent } from "../utils";

  export let choices: string[];
  export let answer: Message | null;
  export let withExplanation: boolean;
  export let questionId: string;

  const radioGroupValues = choices.map((c) => ({ value: c, label: c }));

  let { checked, explanations } = deserializeMessageContent(answer?.data.content ?? null);

  const answerId = answer?.id ?? null;

  let selectedValue: string = radioGroupValues[checked.indexOf(true)]?.value;
  /* eslint-disable-next-line @typescript-eslint/no-unused-expressions */
  $: selectedValue, handleContentChange();

  const dispatch = createEventDispatcher();

  const handleContentChange = () => {
    const content = serializeMessageContent({ choices: [selectedValue], explanations });

    const eventDetail: ContentChangeEvent = answerId
      ? {
          content,
          type: ContentChangeEventType.UPDATE,
          answerId,
        }
      : {
          content,
          type: ContentChangeEventType.NEW_ANSWER,
          questionId,
        };

    dispatch("answerContentChange", eventDetail);
  };
</script>

<div class="p-2 border border-slate-100 rounded-lg flex flex-col gap-3">
  <div class="flex flex-row gap-2 items-center">
    <RadioGroup bind:selectedValue values={radioGroupValues} />
  </div>
  {#if withExplanation}
    <input
      type="text"
      placeholder="Explanations"
      class="p-2 text-slate-800 placeholder-slate-500 outline-none border border-slate-100 rounded-lg"
      bind:value={explanations}
      on:blur={handleContentChange}
    />
  {/if}
</div>
