<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { Message } from "$lib/types/dataset";
  import { Checkbox } from "bits-ui";
  import { Check } from "phosphor-svelte";

  import { ContentChangeEventType, type ContentChangeEvent } from "$lib/types/vqa";
  import {
    checkboxsStateToAnswerChoices,
    deserializeMessageContent,
    serializeMessageContent,
  } from "./utils";

  interface Props {
    choices: string[];
    answer: Message | null;
    withExplanation: boolean;
    questionId: string;
    disabled?: boolean;
    onAnswerContentChange?: (event: ContentChangeEvent) => void;
  }

  let {
    choices,
    answer,
    withExplanation,
    questionId,
    disabled = false,
    onAnswerContentChange,
  }: Props = $props();

  let checked = $state<boolean[]>([]);
  let explanations = $state("");

  $effect(() => {
    const parsed = deserializeMessageContent(answer?.data.content ?? null);
    checked = parsed.checked;
    explanations = parsed.explanations;
  });

  const handleCheckboxChange = (index: number, isChecked: boolean) => {
    if (disabled) return;
    checked[index] = isChecked;
    handleContentChange();
  };

  const handleContentChange = () => {
    if (disabled) return;
    const selectedChoices = checkboxsStateToAnswerChoices(checked);
    const content = serializeMessageContent({ choices: selectedChoices, explanations });
    const answerId = answer?.id ?? null;

    const eventDetail: ContentChangeEvent = answerId
      ? { content, type: ContentChangeEventType.UPDATE, answerId }
      : {
          content,
          type: ContentChangeEventType.NEW_ANSWER,
          questionId,
        };

    onAnswerContentChange?.(eventDetail);
  };
</script>

<div class="flex flex-col gap-3 {disabled ? 'pointer-events-none opacity-70' : ''}">
  {#each choices as choice, index}
    <div class="flex flex-row gap-2 items-center">
      <Checkbox.Root
        {disabled}
        checked={checked[index]}
        onCheckedChange={(c) => {
          handleCheckboxChange(index, c);
        }}
        class="peer h-4 w-4 shrink-0 rounded border border-primary ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground data-[disabled]:cursor-not-allowed data-[disabled]:opacity-50"
      >
        {#snippet children({ checked: isChecked })}
          <span class="flex items-center justify-center text-current h-full w-full">
            {#if isChecked}
              <Check class="h-3.5 w-3.5"  />
            {/if}
          </span>
        {/snippet}
      </Checkbox.Root>
      <span class="text-sm text-slate-700">{choice}</span>
    </div>
  {/each}
  {#if withExplanation}
    <div class="mt-2 pt-2 border-t border-primary/10">
      <input
        type="text"
        placeholder="Provide an explanation..."
        class="w-full bg-transparent p-0 text-sm text-slate-700 outline-none placeholder:text-slate-300 italic {disabled
          ? 'cursor-default'
          : ''}"
        bind:value={explanations}
        onblur={handleContentChange}
        {disabled}
      />
    </div>
  {/if}
</div>
