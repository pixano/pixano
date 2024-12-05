<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { cn, TaggedText } from "@pixano/core";
  import { getNewTaggedText } from "./getNewTaggedText";
  import { getSelectedText } from "./getSelectedText";
  import { getSelection } from "./getSelection";
  import { tagSelectedText } from "./htmlTextTagger";

  let taggedTexts: TaggedText[] = [];

  // To avoid importing nanoid package
  // TODO: update objectsApi
  let taggedTextId = 0;

  const handleClick = () => {
    const { selection, range } = getSelection();
    const selectedText = getSelectedText(selection);

    const newTaggedText = getNewTaggedText(taggedTextId.toString(), selectedText);
    ++taggedTextId;

    taggedTexts = [...taggedTexts, newTaggedText];

    newTaggedText.ui.bgColor = "black";

    const metadata = {
      id: newTaggedText.id,
      bgColor: newTaggedText.ui.bgColor,
    };

    tagSelectedText({
      selection,
      range,
      selectedText,
      tagName: "span",
      metadata,
      className: `text-white rounded-md p-1 bg-${newTaggedText.ui.bgColor}`,
    });
  };
</script>

<div class={cn("bg-white p-2 flex flex-col gap-2")}>
  <button
    class={cn("bg-slate-800 text-white p-2 rounded-md w-fit")}
    on:click={handleClick}
    id="tagButton">Tag Selected Text</button
  >

  <div id="content" contenteditable="true">
    This is some editable text. Select any text and tag it with custom metadata!
  </div>
</div>
