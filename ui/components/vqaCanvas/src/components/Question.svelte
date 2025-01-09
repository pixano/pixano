<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { cn, type Message } from "@pixano/core";

  export let message: Message;
</script>

<div class={cn("font-semibold")}>{message.data.content}</div>
