<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { QuestionTypeEnum, RadioGroup } from "@pixano/core";

  export let questionType: QuestionTypeEnum;

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
  <RadioGroup
    bind:selectedValue={questionType}
    values={availableQuestionTypes}
    itemClass="text-foreground text-base font-normal"
  />
</div>
