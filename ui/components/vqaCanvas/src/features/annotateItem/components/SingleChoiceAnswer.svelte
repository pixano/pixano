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
  export let disabled = false;

  const radioGroupValues = choices.map((c) => ({ value: c, label: c }));

  let { checked, explanations } = deserializeMessageContent(answer?.data.content ?? null);

  const answerId = answer?.id ?? null;

  let selectedValue: string = radioGroupValues[checked.indexOf(true)]?.value;
  /* eslint-disable-next-line @typescript-eslint/no-unused-expressions */
  $: selectedValue, handleContentChange();

  const dispatch = createEventDispatcher();

  const handleContentChange = () => {
    if (disabled) return;
    const index = choices.indexOf(selectedValue);
    if (index === -1) return;
    const label = String.fromCharCode(index + 65);
    const content = serializeMessageContent({ choices: [label], explanations });

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

<div class="flex flex-col gap-3">
  <div class="flex flex-col gap-1">
    <RadioGroup
      bind:selectedValue
      values={radioGroupValues}
      class="flex flex-col gap-2"
      {disabled}
    />
  </div>
  {#if withExplanation}
    <div class="mt-2 pt-2 border-t border-primary/10">
      <input
        type="text"
        placeholder="Provide an explanation..."
        class="w-full bg-transparent p-0 text-sm text-slate-700 outline-none placeholder:text-slate-300 italic {disabled
          ? 'cursor-default'
          : ''}"
        bind:value={explanations}
        on:blur={handleContentChange}
        {disabled}
      />
    </div>
  {/if}
</div>
