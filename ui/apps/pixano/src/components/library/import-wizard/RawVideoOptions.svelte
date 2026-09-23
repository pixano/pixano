<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { validateRawVideoOptions, type RawFields } from "./rawSchema";
  import { WIZARD_INPUT_CLASS } from "./wizardStyles";

  interface Props {
    raw: RawFields;
  }

  let { raw = $bindable() }: Props = $props();
  const folderEncoding = $derived(raw.layout?.ok === true && raw.layout.encoding === "folders");
  const validationError = $derived(validateRawVideoOptions(raw));
  const inputClass = WIZARD_INPUT_CLASS;
</script>

{#if raw.task === "video"}
  <fieldset class="min-w-0 space-y-3">
    <legend class="text-sm font-semibold text-foreground">Video handling</legend>
    {#if folderEncoding}
      <p class="text-xs leading-relaxed text-muted-foreground">
        Each frame folder defines one video sequence.
      </p>
    {:else}
      <label class="block space-y-1.5">
        <span class="text-sm font-medium text-foreground">Import videos as</span>
        <select class={inputClass} bind:value={raw.framesMode}>
          <option value="extract">Extract frames</option>
          <option value="reference">Video references (metadata only)</option>
        </select>
      </label>
    {/if}

    {#if folderEncoding || raw.framesMode === "extract"}
      <div class="space-y-3">
        <label class="block space-y-1.5">
          <span class="text-sm font-medium text-foreground">Max frames per video (optional)</span>
          <input
            type="text"
            inputmode="numeric"
            class={inputClass}
            placeholder="All frames"
            bind:value={raw.maxFrames}
            aria-label="Max frames per video"
          />
        </label>
        <p class="text-xs leading-relaxed text-muted-foreground">
          Frames are sampled uniformly up to this limit.
        </p>
        <label class="block space-y-1.5">
          <span class="text-sm font-medium text-foreground">
            {folderEncoding ? "Frames per second" : "Sampling frames per second"} (optional)
          </span>
          <input
            type="text"
            inputmode="decimal"
            class={inputClass}
            placeholder={folderEncoding ? "Unknown" : "Original frame rate"}
            bind:value={raw.fps}
            aria-label={folderEncoding ? "Frames per second" : "Sampling frames per second"}
          />
        </label>
        <p class="text-xs leading-relaxed text-muted-foreground">
          {folderEncoding
            ? "Sets frame timestamps. Leave empty if unknown."
            : "Sampling rate. Leave empty to preserve the source frame rate."}
        </p>
      </div>
    {:else}
      <p class="text-xs leading-relaxed text-muted-foreground">
        Stores metadata and file references. Playback is not supported in this release. Select
        “Extract frames” to annotate or browse frames.
      </p>
    {/if}
    {#if validationError}
      <p class="text-sm text-destructive" role="alert">{validationError}</p>
    {/if}
  </fieldset>
{/if}
