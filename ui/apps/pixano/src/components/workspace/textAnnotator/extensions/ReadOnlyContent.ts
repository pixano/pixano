/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { Extension } from "@tiptap/core";
import { Plugin, PluginKey } from "@tiptap/pm/state";

export const MARK_UPDATE_META = "textSpanMarkUpdate";

export const ReadOnlyContent = Extension.create({
  name: "readOnlyContent",

  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: new PluginKey("readOnlyContent"),
        filterTransaction(tr) {
          if (tr.getMeta(MARK_UPDATE_META)) return true;
          if (!tr.docChanged) return true;
          return false;
        },
        props: {
          handleKeyDown: () => true,
          handleKeyPress: () => true,
          handlePaste: () => true,
          handleDrop: () => true,
        },
      }),
    ];
  },
});
