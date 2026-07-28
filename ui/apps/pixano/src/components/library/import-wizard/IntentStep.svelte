<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Database, Images, MagicWand, Robot, Tag } from "phosphor-svelte";

  import type { ImportIntent } from "./wizardUtils";
  import { intentToFormat } from "./wizardUtils";
  import type { IoFormatResponse } from "$lib/api/restTypes";

  interface Props {
    formats: IoFormatResponse[] | null;
    onSelect: (intent: ImportIntent) => void;
  }

  let { formats, onSelect }: Props = $props();

  const CARDS: { intent: ImportIntent; title: string; blurb: string; icon: typeof Images }[] = [
    {
      intent: "raw",
      title: "Raw media",
      blurb:
        "Start annotating from scratch: folders of images, videos, or text files — you define the schema.",
      icon: Images,
    },
    {
      intent: "pixano_jsonl",
      title: "Pixano dataset",
      blurb:
        "A JSONL v2 export or any source with a dataset.yaml — schema and annotations included.",
      icon: Database,
    },
    {
      intent: "coco",
      title: "MS COCO",
      blurb: "COCO instances JSON + images; categories become entity attributes.",
      icon: Tag,
    },
    {
      intent: "lerobot",
      title: "LeRobot",
      blurb: "Robotics episodes (v2.1 / v3), from a local folder or the Hugging Face hub.",
      icon: Robot,
    },
  ];

  /** An intent is offered once /io/formats confirms its backend format imports. */
  function available(intent: ImportIntent): boolean {
    if (formats === null) return true; // optimistic while loading
    const format = intentToFormat(intent);
    return formats.some((f) => f.name === format && f.can_import);
  }
</script>

<div class="px-6 sm:px-7 pb-2 space-y-3">
  <div class="grid gap-2 sm:grid-cols-2">
    {#each CARDS as card (card.intent)}
      {@const enabled = available(card.intent)}
      <button
        type="button"
        class="rounded-xl border border-border bg-card p-4 text-left transition-colors hover:border-primary/50 disabled:cursor-not-allowed disabled:opacity-50"
        disabled={!enabled}
        onclick={() => onSelect(card.intent)}
      >
        <span class="flex items-center gap-2 text-sm font-medium text-foreground">
          <card.icon weight="regular" class="h-5 w-5 shrink-0 text-primary" />
          {card.title}
        </span>
        <span class="mt-1.5 block text-xs leading-relaxed text-muted-foreground">{card.blurb}</span>
      </button>
    {/each}
  </div>

  <button
    type="button"
    class="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
    onclick={() => onSelect("auto")}
  >
    <MagicWand weight="regular" class="h-3.5 w-3.5" />
    Not sure? Let Pixano detect the format.
  </button>
</div>
