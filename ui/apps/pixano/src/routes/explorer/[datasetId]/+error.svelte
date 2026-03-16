<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { goto } from "$app/navigation";
  import { page } from "$app/state";
  import { PrimaryButton } from "$lib/ui";
</script>

<div class="w-full pt-40 text-center flex flex-col gap-5 items-center">
  <h1 class="text-4xl font-bold text-foreground">{page.status}</h1>
  <p class="text-muted-foreground">{page.error?.message ?? "Something went wrong"}</p>
  <PrimaryButton onclick={() => goto("/")}>Back to library</PrimaryButton>
</div>
