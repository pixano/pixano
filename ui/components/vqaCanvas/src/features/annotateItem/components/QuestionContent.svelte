<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { cn } from "@pixano/core";

  export let content: string;
</script>

<p class={cn("text-muted-foreground")}>{content}</p>
