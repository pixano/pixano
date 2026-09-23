<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { ChatsCircle, Images, LinkSimple, VideoCamera } from "phosphor-svelte";

  import type { RawTask } from "./layoutPreflight";
  import WizardChoiceCard from "./WizardChoiceCard.svelte";
  import { WIZARD_LABEL_CLASS } from "./wizardStyles";

  interface Props {
    selected: RawTask;
    onSelect: (task: RawTask) => void;
  }
  let { selected, onSelect }: Props = $props();

  const choices: {
    task: RawTask;
    title: string;
    description: string;
    icon: typeof Images;
  }[] = [
    {
      task: "image",
      title: "Image annotation",
      description: "Boxes, masks, polygons.",
      icon: Images,
    },
    {
      task: "video",
      title: "Video annotation",
      description: "Object tracks across frames.",
      icon: VideoCamera,
    },
    {
      task: "image_vqa",
      title: "Visual Q&A",
      description: "Image questions and answers.",
      icon: ChatsCircle,
    },
    {
      task: "image_text_entity_linking",
      title: "Image–text linking",
      description: "Link text spans to image regions.",
      icon: LinkSimple,
    },
  ];
</script>

<fieldset class="min-w-0 space-y-2">
  <legend class={WIZARD_LABEL_CLASS}>Annotation task</legend>
  <div class="grid grid-cols-2 gap-2">
    {#each choices as choice (choice.task)}
      <WizardChoiceCard
        icon={choice.icon}
        title={choice.title}
        description={choice.description}
        selected={selected === choice.task}
        onclick={() => onSelect(choice.task)}
      />
    {/each}
  </div>
</fieldset>
