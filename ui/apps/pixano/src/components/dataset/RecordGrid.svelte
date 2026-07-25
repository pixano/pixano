<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import RecordCard from "./RecordCard.svelte";
  import type { RecordCard as RecordCardType } from "$lib/types/dataset";

  interface Props {
    cards: RecordCardType[];
    /** Ranked (semantic / find-similar) mode: show rank + distance chips. */
    ranked?: boolean;
    onOpen: (id: string) => void;
    onFindSimilar?: (id: string) => void;
  }

  let { cards, ranked = false, onOpen, onFindSimilar }: Props = $props();
</script>

<div class="w-full h-full overflow-y-auto">
  <div
    class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-4 p-4"
  >
    {#each cards as card, i (card.id)}
      <div class="animate-in fade-in slide-in-from-bottom-2 duration-500">
        <RecordCard record={card} rank={ranked ? i + 1 : undefined} {onOpen} {onFindSimilar} />
      </div>
    {/each}
  </div>
</div>
