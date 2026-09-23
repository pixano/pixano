<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Select } from "bits-ui";
  import { CaretDown, Check, CircleNotch } from "phosphor-svelte";

  import * as api from "$lib/api";
  import { RECORD_STATUS_LABELS, RECORD_STATUSES, type RecordStatus } from "$lib/api/records";

  interface Props {
    datasetId: string;
    recordId: string;
  }

  let { datasetId, recordId }: Props = $props();

  let status = $state<RecordStatus | "">("");
  let saving = $state(false);
  let saveError = $state(false);

  // Status writes immediately (its own contract, independent of the batched annotation save).
  // Load the record's current status whenever the record changes.
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

  async function applyStatus(next: RecordStatus) {
    if (next === status) return;
    const previous = status;
    status = next; // optimistic
    saving = true;
    saveError = false;
    try {
      await api.updateRecordStatus(datasetId, recordId, next);
    } catch {
      status = previous; // revert on failure — and say so
      saveError = true;
      setTimeout(() => (saveError = false), 4000);
    } finally {
      saving = false;
    }
  }

  // Status tone dots (semantic tokens only).
  const toneClass: Record<RecordStatus, string> = {
    new: "bg-muted-foreground/40",
    inProgress: "bg-info",
    inReview: "bg-warning",
    validated: "bg-success",
  };
</script>

{#if status !== ""}
  <div class="flex flex-col gap-1.5">
    <Select.Root
      type="single"
      value={status}
      onValueChange={(next) => {
        if (next) void applyStatus(next as RecordStatus);
      }}
    >
      <Select.Trigger
        aria-label="Record status"
        disabled={saving}
        class="inline-flex h-10 w-full items-center justify-between gap-2 rounded-xl border border-input bg-background px-3 text-sm shadow-sm transition-colors hover:bg-accent/40 disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {#snippet children()}
          <span class="flex min-w-0 items-center gap-2">
            <span
              class="h-2.5 w-2.5 shrink-0 rounded-full {toneClass[status as RecordStatus]}"
            ></span>
            <span class="truncate">{RECORD_STATUS_LABELS[status as RecordStatus]}</span>
          </span>
          {#if saving}
            <CircleNotch size={13} class="shrink-0 animate-spin text-muted-foreground" />
          {:else}
            <CaretDown size={13} class="shrink-0 text-muted-foreground" />
          {/if}
        {/snippet}
      </Select.Trigger>
      <Select.Portal>
        <Select.Content
          sideOffset={6}
          class="z-50 rounded-2xl border border-border/50 bg-popover/95 p-1.5 text-popover-foreground shadow-elevation-2 backdrop-blur-md"
        >
          {#each RECORD_STATUSES as value (value)}
            <Select.Item
              {value}
              label={RECORD_STATUS_LABELS[value]}
              class="flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 text-sm outline-none transition-colors data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground"
            >
              {#snippet children()}
                <span class="h-2.5 w-2.5 shrink-0 rounded-full {toneClass[value]}"></span>
                <span class="flex-1 truncate text-left">{RECORD_STATUS_LABELS[value]}</span>
                {#if status === value}<Check size={13} class="shrink-0 text-primary" />{/if}
              {/snippet}
            </Select.Item>
          {/each}
        </Select.Content>
      </Select.Portal>
    </Select.Root>
    {#if saveError}
      <p class="text-left text-xs text-destructive">Couldn't update the status — reverted.</p>
    {/if}
  </div>
{/if}
