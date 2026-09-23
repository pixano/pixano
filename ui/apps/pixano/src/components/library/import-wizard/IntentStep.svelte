<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Check, Database, Images, MagicWand, Robot, Tag } from "phosphor-svelte";

  import WizardChoiceCard from "./WizardChoiceCard.svelte";
  import { WIZARD_LABEL_CLASS } from "./wizardStyles";
  import { intentToFormat, type ImportIntent } from "./wizardUtils";
  import type { IoFormatResponse } from "$lib/api/restTypes";

  interface Props {
    formats: IoFormatResponse[] | null;
    selected: ImportIntent | null;
    onSelect: (intent: ImportIntent) => void;
  }

  let { formats, selected, onSelect }: Props = $props();

  const choices: {
    intent: ImportIntent;
    title: string;
    description: string;
    icon: typeof Images;
  }[] = [
    {
      intent: "raw",
      title: "Raw media",
      description: "Images, videos, or image–text pairs.",
      icon: Images,
    },
    {
      intent: "lerobot",
      title: "LeRobot",
      description: "Robot episodes (folder or Hub).",
      icon: Robot,
    },
    {
      intent: "coco",
      title: "MS COCO",
      description: "Images with COCO annotations.",
      icon: Tag,
    },
    {
      intent: "pixano_jsonl",
      title: "Pixano dataset",
      description: "Existing schema and annotations.",
      icon: Database,
    },
  ];
</script>

<fieldset class="min-w-0 space-y-2">
  <legend class={WIZARD_LABEL_CLASS}>Data format</legend>
  <div class="grid grid-cols-2 gap-2">
    {#each choices as choice (choice.intent)}
      <WizardChoiceCard
        icon={choice.icon}
        title={choice.title}
        description={choice.description}
        selected={selected === choice.intent}
        disabled={formats !== null &&
          !formats.some(
            (format) => format.name === intentToFormat(choice.intent) && format.can_import,
          )}
        onclick={() => onSelect(choice.intent)}
      />
    {/each}
  </div>
  <button
    type="button"
    class={`inline-flex min-h-8 items-center gap-2 rounded text-xs font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background ${selected === "auto" ? "text-primary" : "text-muted-foreground hover:text-foreground"}`}
    aria-pressed={selected === "auto"}
    onclick={() => onSelect("auto")}
  >
    <MagicWand size={16} weight="regular" aria-hidden="true" />
    Detect automatically
    {#if selected === "auto"}<Check size={14} weight="bold" aria-hidden="true" />{/if}
  </button>
</fieldset>
