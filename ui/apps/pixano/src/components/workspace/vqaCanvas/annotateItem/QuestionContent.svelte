<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { cn } from "$lib/utils/styleUtils";

  interface Props {
    content: string;
  }

  let { content }: Props = $props();
</script>

<p class={cn("text-muted-foreground")}>{content}</p>
