/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { Mark } from "@tiptap/core";
import { Plugin, PluginKey } from "@tiptap/pm/state";

export interface TextSpanMarkOptions {
  onSpanClick: (id: string) => void;
}

export const TextSpanMark = Mark.create<TextSpanMarkOptions>({
  name: "textSpanMark",

  inclusive: false,

  addOptions() {
    return {
      onSpanClick: () => {},
    };
  },

  addAttributes() {
    return {
      id: { default: null },
      entityId: { default: null },
      bgColor: { default: null },
      textColor: { default: null },
      hidden: { default: false },
      highlighted: { default: false },
    };
  },

  parseHTML() {
    return [{ tag: "span[data-text-span-id]" }];
  },

  renderHTML({ HTMLAttributes }) {
    const { id, entityId, bgColor, textColor, hidden, highlighted } = HTMLAttributes;

    const style = hidden
      ? "background-color: transparent; color: black; padding: 1px 4px; border-radius: 6px; margin: 0px 1px;"
      : [
          `background-color: ${bgColor};`,
          `color: ${textColor};`,
          "padding: 1px 4px;",
          "border-radius: 6px;",
          "margin: 0px 1px;",
          highlighted ? `box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.2), 0 0 10px ${bgColor};` : "",
        ].join(" ");

    return [
      "span",
      {
        "data-text-span-id": id,
        "data-entity-id": entityId,
        style,
      },
      0,
    ];
  },

  addProseMirrorPlugins() {
    const { onSpanClick } = this.options;

    return [
      new Plugin({
        key: new PluginKey("textSpanMarkClick"),
        props: {
          handleClick(view, pos) {
            const { state } = view;
            const resolved = state.doc.resolve(pos);
            const marks = resolved.marks();
            const spanMark = marks.find((m) => m.type.name === "textSpanMark");
            if (spanMark?.attrs.id) {
              onSpanClick(spanMark.attrs.id);
              return true;
            }
            return false;
          },
        },
      }),
    ];
  },
});
