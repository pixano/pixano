<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { X } from "phosphor-svelte";

  import JobsPanel from "./JobsPanel.svelte";
  import type { JobTarget } from "$lib/api/jobsApi";

  type Props = {
    /** The dataset the explorer shows — the one a job launched here runs on. */
    dataset: JobTarget;
    onClose: () => void;
  };
  let { dataset, onClose }: Props = $props();

  function handleKeyDown(event: KeyboardEvent) {
    if (event.key === "Escape") onClose();
  }
</script>

<svelte:window onkeydown={handleKeyDown} />

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
  onclick={onClose}
>
  <div
    role="dialog"
    aria-modal="true"
    aria-labelledby="jobs-modal-title"
    tabindex="-1"
    onclick={(event) => event.stopPropagation()}
    class="flex h-[90vh] w-[30rem] flex-col overflow-hidden rounded-2xl border border-border/50 bg-card text-foreground shadow-2xl"
  >
    <div class="flex items-center justify-between border-b border-border px-4 py-3">
      <h2 id="jobs-modal-title" class="text-base font-semibold">Jobs</h2>
      <button
        type="button"
        aria-label="Close"
        onclick={onClose}
        class="flex h-7 w-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
      >
        <X weight="regular" size={16} />
      </button>
    </div>
    <div class="min-h-0 flex-1">
      <JobsPanel {dataset} />
    </div>
  </div>
</div>
