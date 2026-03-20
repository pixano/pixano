<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<!--
  DEPRECATED: TextSpan annotations are now rendered inline within ChildCard.svelte
  via the type-specific visualization system. This component is kept as an empty shell
  for backward compatibility but no longer renders any content.
-->

<script lang="ts">
  import type { Annotation } from "$lib/types/dataset";

  interface Props {
    annotations: Annotation[] | undefined;
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  let { annotations: _annotations }: Props = $props();
</script>

<!-- Intentionally empty: TextSpan content is now displayed in ChildCard -->
