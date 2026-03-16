<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Label, RadioGroup } from "bits-ui";
  import { Check } from "phosphor-svelte";
  import { untrack } from "svelte";

  import { deserializeMessageContent, serializeMessageContent } from "./utils";
  import type { Message } from "$lib/types/dataset";
  import { ContentChangeEventType, type ContentChangeEvent } from "$lib/types/vqa";
  import { effectProbe } from "$lib/utils/effectProbe";
  import { cn } from "$lib/utils/styleUtils";

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

  const radioGroupValues = $derived(choices.map((choice) => ({ value: choice, label: choice })));

  let checked = $state<boolean[]>([]);
  let explanations = $state("");
  let selectedValue = $state<string>("");
  let lastCommittedValue = $state<string>("");

  $effect(() => {
    const answerContent = answer?.data.content ?? null;
    const rgValues = radioGroupValues;
    untrack(() => {
      effectProbe("SingleChoiceAnswer.hydrate", {
        answerId: answer?.id ?? null,
        choicesCount: choices.length,
      });
      const parsed = deserializeMessageContent(answerContent);
      checked = parsed.checked;
      explanations = parsed.explanations;
      const syncedValue = rgValues[parsed.checked.indexOf(true)]?.value ?? "";
      selectedValue = syncedValue;
      lastCommittedValue = syncedValue;
    });
  });

  const handleContentChange = () => {
    if (disabled) return;
    const index = choices.indexOf(selectedValue);
    if (index === -1) return;
    const label = String.fromCharCode(index + 65);
    const content = serializeMessageContent({ choices: [label], explanations });
    const messageId = answer?.id ?? null;

    const eventDetail: ContentChangeEvent = messageId
      ? {
          content,
          type: ContentChangeEventType.UPDATE,
          messageId,
        }
      : {
          content,
          type: ContentChangeEventType.NEW_ANSWER,
          questionId,
        };

    onAnswerContentChange?.(eventDetail);
  };
  $effect(() => {
    const currentValue = selectedValue;
    untrack(() => {
      effectProbe("SingleChoiceAnswer.commitSelection", {
        answerId: answer?.id ?? null,
        selectedValue: currentValue,
        lastCommittedValue,
      });
      if (currentValue === lastCommittedValue) return;
      lastCommittedValue = currentValue;
      handleContentChange();
    });
  });
</script>

<div class="flex flex-col gap-3">
  <div class="flex flex-col gap-1">
    <RadioGroup.Root
      class="flex flex-col gap-4 text-sm font-medium {disabled
        ? 'pointer-events-none opacity-70'
        : ''}"
      bind:value={selectedValue}
      {disabled}
    >
      {#each radioGroupValues as { label, value }}
        <div
          class={cn("group flex select-none items-center text-foreground transition-all", "gap-2")}
        >
          <RadioGroup.Item
            id={value}
            {value}
            {disabled}
            class="size-5 shrink-0 rounded-full border border-primary transition-all duration-100 ease-in-out data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground flex items-center justify-center"
          >
            {#snippet children({ checked })}
              {#if checked}<Check class="h-3.5 w-3.5" />{/if}
            {/snippet}
          </RadioGroup.Item>
          <Label.Root for={value} class="pl-3">{label}</Label.Root>
        </div>
      {/each}
    </RadioGroup.Root>
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
        onblur={handleContentChange}
        {disabled}
      />
    </div>
  {/if}
</div>
