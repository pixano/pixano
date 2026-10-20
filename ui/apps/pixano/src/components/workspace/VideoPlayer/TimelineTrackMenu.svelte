<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // The items of the timeline's track menu, for the tracks under the right-clicked frame:
  // edit, add or remove a keyframe there, split, glue, relink or delete. Destructive items
  // take a second click, as in the canvas chip; keys typed in the menu stay in it.
  import { ContextMenu } from "bits-ui";

  import RelinkAnnotation from "../SaveShape/RelinkAnnotation.svelte";
  import type { TimelineMenuTarget } from "./timelineContext";
  import { mediaViews, tracks } from "$lib/stores/workspaceStores.svelte";
  import { trackMenuAvailability, trackMenuHeading } from "$lib/timeline/timelineMenu";
  import type { BoxAction } from "$lib/types/boxActions";
  import { BaseSchema, type Tracklet } from "$lib/types/dataset";
  import { trackActionsAt } from "$lib/utils/boxActions";
  import { editTrack } from "$lib/utils/editMode";
  import { getTopEntity } from "$lib/utils/entityLookupUtils";
  import { relink } from "$lib/utils/entityRelink";
  import { cn } from "$lib/utils/styleUtils";
  import { seekTimeline } from "$lib/utils/timelineActions";
  import { glueTracklets, interpolatedShapesAt } from "$lib/utils/trackletOperations";
  import { getWorkspaceContext } from "$lib/workspace/context";

  interface Props {
    target: TimelineMenuTarget;
    /** Why the timeline's actions are off now, or null. */
    blockedReason: string | null;
    onClose: () => void;
  }

  let { target, blockedReason, onClose }: Props = $props();

  const { manifest } = getWorkspaceContext();

  interface MenuItem {
    key: string;
    label: string;
    destructive?: boolean;
    confirmLabel?: string;
    /** Keep the menu open after running (the inline relink form). */
    keepOpen?: boolean;
    run: () => void;
  }

  const EDITABLE_SCHEMAS = [BaseSchema.BBox, BaseSchema.Keypoints];
  const CONFIRM_TIMEOUT_MS = 3000;

  let confirmingKey = $state<string | null>(null);
  let confirmTimer: ReturnType<typeof setTimeout> | null = null;
  let relinkTrackletId = $state<string | null>(null);
  let selectedEntityId = $state("new");
  let mustMerge = $state(false);
  let overlapTargetId = $state("");

  function distinctFrames(tracklet: Tracklet, keep: (schema: BaseSchema) => boolean): number[] {
    const frames = new Set<number>();
    for (const child of tracklet.ui.childs ?? []) {
      if (typeof child.ui.frame_index === "number" && keep(child.table_info.base_schema)) {
        frames.add(child.ui.frame_index);
      }
    }
    return [...frames].sort((a, b) => a - b);
  }

  function menuTrack(tracklet: Tracklet) {
    return {
      id: tracklet.id,
      view: tracklet.data.view_name,
      start: Math.min(tracklet.data.start_frame, tracklet.data.end_frame),
      end: Math.max(tracklet.data.start_frame, tracklet.data.end_frame),
      keyframes: distinctFrames(tracklet, () => true),
      editableFrames: distinctFrames(tracklet, (schema) => EDITABLE_SCHEMAS.includes(schema)),
    };
  }

  function fromBoxAction(trackletId: string, action: BoxAction): MenuItem {
    return {
      key: `${trackletId}:${action.id}`,
      label: action.label,
      destructive: action.destructive,
      confirmLabel: action.confirmLabel,
      run: action.run,
    };
  }

  const groups = $derived.by(() => {
    if (blockedReason) return [];
    const ownTracks = tracks.value.filter(
      (tracklet) => tracklet.data.entity_id === target.entity.id,
    );
    const ownMenuTracks = ownTracks.map(menuTrack);
    const frame = target.frame;
    return target.tracks.map((tracklet) => {
      const track = menuTrack(tracklet);
      const can = trackMenuAvailability(track, ownMenuTracks, frame);
      const ghosts = interpolatedShapesAt(tracklet, frame, mediaViews.value);
      const hasGhost = ghosts.bboxes.length > 0 || ghosts.keypoints.length > 0;
      const boxActions = trackActionsAt(tracklet, target.entity, frame, {
        ghosts: hasGhost ? ghosts : undefined,
      });
      const items: MenuItem[] = [];
      if (can.canEdit) {
        items.push({
          key: `${tracklet.id}:edit`,
          label: `Edit keyframe #${frame}`,
          run: () => {
            seekTimeline(frame);
            editTrack(tracklet.id, { reveal: false });
          },
        });
      }
      const deleteAction = boxActions.find((action) => action.id === "delete-track");
      for (const action of boxActions) {
        if (action !== deleteAction) items.push(fromBoxAction(tracklet.id, action));
      }
      for (const [neighborId, label] of [
        [can.glueBefore, "Glue to the track before"],
        [can.glueAfter, "Glue to the track after"],
      ] as const) {
        const neighbor = neighborId ? ownTracks.find((t) => t.id === neighborId) : undefined;
        if (neighbor) {
          items.push({
            key: `${tracklet.id}:glue:${neighbor.id}`,
            label,
            run: () => glueTracklets(tracklet, neighbor, target.entity.id),
          });
        }
      }
      items.push({
        key: `${tracklet.id}:relink`,
        label: "Relink track…",
        keepOpen: true,
        run: () => {
          selectedEntityId = "new";
          mustMerge = false;
          overlapTargetId = "";
          relinkTrackletId = relinkTrackletId === tracklet.id ? null : tracklet.id;
        },
      });
      if (deleteAction) items.push(fromBoxAction(tracklet.id, deleteAction));
      return { tracklet, heading: trackMenuHeading(track), items };
    });
  });

  function clearConfirm() {
    if (confirmTimer) clearTimeout(confirmTimer);
    confirmTimer = null;
    confirmingKey = null;
  }

  function select(event: Event, item: MenuItem) {
    if (item.destructive && confirmingKey !== item.key) {
      event.preventDefault();
      clearConfirm();
      confirmingKey = item.key;
      confirmTimer = setTimeout(clearConfirm, CONFIRM_TIMEOUT_MS);
      return;
    }
    clearConfirm();
    if (item.keepOpen) event.preventDefault();
    item.run();
  }

  function confirmRelink(tracklet: Tracklet) {
    relink(
      tracklet,
      getTopEntity(tracklet),
      selectedEntityId,
      mustMerge,
      overlapTargetId,
      manifest,
    );
    relinkTrackletId = null;
    onClose();
  }

  $effect(() => () => clearConfirm());

  const itemClass =
    "flex cursor-pointer items-center rounded-md px-2 py-1 text-xs outline-none transition-colors data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground";
  const headingClass =
    "px-2 pb-0.5 pt-1.5 font-mono text-[10px] font-semibold tracking-wide text-foreground/65";
</script>

{#if blockedReason}
  <div class="px-2 py-1 text-xs text-foreground/65">{blockedReason}</div>
{:else}
  {#each groups as group, index (group.tracklet.id)}
    {#if index > 0}
      <ContextMenu.Separator class="my-1 h-px bg-border" />
    {/if}
    {#if groups.length > 1}
      <ContextMenu.Group>
        <ContextMenu.GroupHeading class={headingClass}>{group.heading}</ContextMenu.GroupHeading>
      </ContextMenu.Group>
    {/if}
    {#each group.items as item (item.key)}
      {@const confirming = confirmingKey === item.key}
      <ContextMenu.Item
        class={cn(
          itemClass,
          item.destructive && "text-destructive data-[highlighted]:text-destructive",
          confirming &&
            "bg-destructive text-destructive-foreground data-[highlighted]:bg-destructive/90 data-[highlighted]:text-destructive-foreground",
        )}
        onSelect={(event) => select(event, item)}
      >
        {confirming ? (item.confirmLabel ?? `Click again: ${item.label}`) : item.label}
      </ContextMenu.Item>
    {/each}
    {#if relinkTrackletId === group.tracklet.id}
      <div class="flex flex-col gap-2 px-2 py-1.5">
        <RelinkAnnotation
          bind:selectedEntityId
          bind:mustMerge
          bind:overlapTargetId
          baseSchema={group.tracklet.table_info.base_schema}
          viewRef={{
            name: group.tracklet.data.view_name,
            id:
              typeof group.tracklet.data.frame_id === "string" ? group.tracklet.data.frame_id : "",
          }}
          track={group.tracklet}
        />
        <button
          type="button"
          class="h-8 self-end rounded-lg bg-primary px-3 text-xs font-medium text-primary-foreground hover:bg-primary/90"
          onclick={() => confirmRelink(group.tracklet)}
        >
          Relink
        </button>
      </div>
    {/if}
  {/each}
{/if}
