<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { RenderComponentConfig } from "./render-component";

  interface Props {
    content: unknown;
  }

  let { content }: Props = $props();
</script>

{#if content instanceof RenderComponentConfig}
  <content.component {...content.props} />
{:else if typeof content === "string" || typeof content === "number"}
  {content}
{/if}
