<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { ChatsCircle, Images, LinkSimple, VideoCamera } from "phosphor-svelte";

  import type { RawTask } from "./layoutPreflight";
  import { TASK_CARDS } from "./rawSchema";

  interface Props {
    onSelect: (task: RawTask) => void;
  }

  let { onSelect }: Props = $props();

  const ICONS: Record<RawTask, typeof Images> = {
    image: Images,
    video: VideoCamera,
    image_vqa: ChatsCircle,
    image_text_entity_linking: LinkSimple,
  };
</script>

<div class="px-6 sm:px-7 pb-2 space-y-3">
  <div class="grid gap-2 sm:grid-cols-2">
    {#each TASK_CARDS as card (card.task)}
      {@const Icon = ICONS[card.task]}
      <button
        type="button"
        class="rounded-xl border border-border bg-card p-4 text-left transition-colors hover:border-primary/50"
        onclick={() => onSelect(card.task)}
      >
        <span class="flex items-center gap-2 text-sm font-medium text-foreground">
          <Icon weight="regular" class="h-5 w-5 shrink-0 text-primary" />
          {card.title}
        </span>
        <span class="mt-1.5 block text-xs leading-relaxed text-muted-foreground">{card.blurb}</span>
        <pre
          class="mt-2 overflow-x-auto rounded-lg bg-surface-2 px-2.5 py-2 font-mono text-[10px] leading-relaxed text-muted-foreground">{card.layoutHint}</pre>
      </button>
    {/each}
  </div>
  <p class="text-xs text-muted-foreground">
    Optional <span class="font-mono">train/ val/ test/</span>
    folders can wrap either shape. Other data (e.g. plain text corpora) imports via the Advanced spec
    or the CLI.
  </p>
</div>
