<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Label, RadioGroup } from "bits-ui";
  import { Check } from "phosphor-svelte";

  import { QuestionTypeEnum } from "$lib/types/dataset";
  import { cn } from "$lib/utils/styleUtils";

  interface Props {
    questionType?: QuestionTypeEnum;
  }

  let { questionType = $bindable(QuestionTypeEnum.OPEN) }: Props = $props();

  const availableQuestionTypes: { value: QuestionTypeEnum; label: string }[] = [
    { value: QuestionTypeEnum.OPEN, label: "Open" },
    { value: QuestionTypeEnum.SINGLE_CHOICE, label: "Single choice without explanation" },
    { value: QuestionTypeEnum.SINGLE_CHOICE_EXPLANATION, label: "Single choice with explanation" },
    { value: QuestionTypeEnum.MULTI_CHOICE, label: "Multiple choice without explanation" },
    { value: QuestionTypeEnum.MULTI_CHOICE_EXPLANATION, label: "Multiple choice with explanation" },
  ];
</script>

<div class="p-3 flex flex-col gap-2">
  <h5 class="font-medium">Question type</h5>
  <RadioGroup.Root class="flex flex-col gap-4 text-sm font-medium" bind:value={questionType}>
    {#each availableQuestionTypes as { label, value }}
      <div
        class={cn(
          "group flex select-none items-center text-foreground transition-all",
          "text-foreground text-base font-normal",
        )}
      >
        <RadioGroup.Item
          id={value}
          {value}
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
