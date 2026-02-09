<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Checkbox } from "@pixano/core";
  // Exports
  export let value: boolean;
</script>

<div class="flex items-center justify-center px-4">
  <Checkbox disabled={true} checked={value} />
</div>
