<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { createEventDispatcher } from "svelte";

  import type { Message } from "@pixano/core";
  import { RadioGroup } from "@pixano/core";

  import type { ContentChangeEvent } from "../lib/types";
  import { serializeMessageContent } from "../lib/utils";

  export let choices: string[];
  export let answer: Message;
  export let withExplanation: boolean;

  const radioGroupValues = choices.map((c) => ({ id: c, value: c }));

  let explanation: string = (answer.data.explanations as string[])[0] ?? "";

  let selectedValue: string;
  $: selectedValue, handleContentChange();

  const dispatch = createEventDispatcher();

  const handleContentChange = () => {
    const newContent = serializeMessageContent({ choices: [selectedValue], explanation });

    const eventDetail: ContentChangeEvent = {
      answerId: answer.id,
      newContent,
      newChoices: [selectedValue],
      explanation,
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
      bind:value={explanation}
      on:blur={handleContentChange}
    />
  {/if}
</div>
