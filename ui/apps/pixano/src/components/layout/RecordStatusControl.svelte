<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import * as api from "$lib/api";
  import { RECORD_STATUS_LABELS, RECORD_STATUSES, type RecordStatus } from "$lib/api/records";

  interface Props {
    datasetId: string;
    recordId: string;
  }

  let { datasetId, recordId }: Props = $props();

  let status = $state<RecordStatus | "">("");
  let saving = $state(false);

  // Load the record's current status whenever the item changes.
  $effect(() => {
    const ds = datasetId;
    const rid = recordId;
    if (!ds || !rid) {
      status = "";
      return;
    }
    let cancelled = false;
    void api.getRecord(ds, rid).then((record) => {
      if (!cancelled) {
        const value = record.status as RecordStatus | undefined;
        status = value && RECORD_STATUSES.includes(value) ? value : "new";
      }
    });
    return () => {
      cancelled = true;
    };
  });

  async function onChange(event: Event) {
    const next = (event.currentTarget as HTMLSelectElement).value as RecordStatus;
    const previous = status;
    status = next; // optimistic
    saving = true;
    try {
      await api.updateRecordStatus(datasetId, recordId, next);
    } catch {
      status = previous; // revert on failure
    } finally {
      saving = false;
    }
  }
</script>

{#if status !== ""}
  <label class="flex items-center gap-1.5" title="Annotation status for this record">
    <span class="text-[9px] text-muted-foreground font-bold uppercase tracking-tighter">
      Status
    </span>
    <select
      value={status}
      onchange={onChange}
      disabled={saving}
      class="h-8 rounded-lg border border-border bg-background px-2 text-xs text-foreground shadow-sm disabled:opacity-50"
    >
      {#each RECORD_STATUSES as value (value)}
        <option {value}>{RECORD_STATUS_LABELS[value]}</option>
      {/each}
    </select>
  </label>
{/if}
