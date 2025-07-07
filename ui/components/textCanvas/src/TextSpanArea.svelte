<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import {
    BaseSchema,
    SaveShapeType,
    TextSpan,
    TextView,
    type Shape,
    type TextSpanAttributes,
    type TextSpanTypeWithViewRef,
  } from "@pixano/core";
  import { temporayTextSpanId } from "@pixano/dataset-item-workspace/src/lib/constants";
  import { annotations } from "@pixano/dataset-item-workspace/src/lib/stores/datasetItemWorkspaceStores";

  import { SpannableTextView } from "./components";
  import { groupTextSpansByViewId } from "./lib";

  // Exports
  export let selectedItemId: string;
  export let newShape: Shape;
  export let colorScale: (value: string) => string;
  export let textSpans: TextSpan[];
  export let textViews: TextView[];

  let textSpanAttributes: TextSpanTypeWithViewRef | null = null;

  $: spansByViewId = groupTextSpansByViewId(textSpans);

  const onTagText = () => {
    if (!textSpanAttributes) return;

    const { view_ref, ...textSpanAttrs } = textSpanAttributes;

    //temporary TextSpan to keep it highlighted while filling form
    annotations.update((anns) => {
      const tempTextSpan = new TextSpan({
        id: temporayTextSpanId,
        data: {
          spans_start: textSpanAttributes?.spans_start as number[],
          spans_end: textSpanAttributes?.spans_end as number[],
          mention: textSpanAttributes?.mention as string,
          inference_metadata: {},
          item_ref: { id: selectedItemId, name: "item" },
          entity_ref: { id: "", name: "" },
          view_ref: textSpanAttributes?.view_ref,
          source_ref: { id: "", name: "" },
        },
        table_info: { name: "not_a_table", group: "annotations", base_schema: BaseSchema.TextSpan },
        created_at: "",
        updated_at: "",
      });
      tempTextSpan.ui.displayControl.highlighted = "self";
      anns.push(tempTextSpan);
      return anns;
    });

    // Changing newShape opens the window for customizing and saving a new
    // anotation in the object inspector
    newShape = {
      viewRef: view_ref,
      itemId: selectedItemId,
      imageWidth: 0,
      imageHeight: 0,
      status: "saving",
      type: SaveShapeType.textSpan,
      attrs: textSpanAttrs as TextSpanAttributes,
    };
  };
</script>

<div class="bg-white p-2 flex flex-col gap-2 h-full">
  <button class="bg-primary text-white p-2 rounded-md w-fit" on:click={onTagText} id="tagButton">
    Tag Selected Text
  </button>
  <div class="overflow-y-auto">
    {#each textViews as textView}
      <SpannableTextView
        {textView}
        {colorScale}
        textSpans={spansByViewId[textView.id]}
        bind:textSpanAttributes
      />
    {/each}
  </div>
</div>
