/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";
import { createMockTextSpan, mockRef } from "../../testing";
import { htmlToTextSpans } from "./htmlToTextSpans";

describe("htmlToTextSpan", () => {
  describe("without message content modification and maximum 1 span", () => {
    it("should return an empty array if the div contains only text", () => {
      const div = document.createElement("div");
      div.innerHTML = "Hello World";

      const textSpans = htmlToTextSpans({
        editableDiv: div,
        prevTextSpans: [],
      });

      expect(textSpans).toEqual([]);
    });

    it("should not update the text spans array - with the div containing a span and no text", () => {
      const div = document.createElement("div");

      const mention = "Hello World";
      div.innerHTML = `<span data-id='span-1'>${mention}</span>`;

      const prevTextSpans = [
        createMockTextSpan({
          id: "span-1",
          data: {
            annotation_ref: mockRef,
            spans_start: [0],
            spans_end: [mention.length - 1],
            mention,
          },
        }),
      ];

      const textSpans = htmlToTextSpans({
        editableDiv: div,
        prevTextSpans,
      });

      expect(textSpans).toStrictEqual(prevTextSpans);
    });

    it("should not update the text spans array - with the div containing a span and some text", () => {
      const div = document.createElement("div");

      const mention = "Hello";
      div.innerHTML = `<span data-id='span-1'>${mention}</span> world`;

      const prevTextSpans = [
        createMockTextSpan({
          id: "span-1",
          data: {
            annotation_ref: mockRef,
            spans_start: [0],
            spans_end: [mention.length - 1],
            mention,
          },
        }),
      ];

      const textSpans = htmlToTextSpans({
        editableDiv: div,
        prevTextSpans,
      });

      expect(textSpans).toStrictEqual(prevTextSpans);
    });
  });

  describe("with message content modification and one span", () => {
    it("should include the change of content in the text spans array - if some text was removed from a span", () => {
      const div = document.createElement("div");

      const newMention = "Hello World";
      div.innerHTML = `<span data-id='span-1'>${newMention}</span>`;

      const mention = "Hello";
      const prevTextSpans = [
        createMockTextSpan({
          id: "span-1",
          data: {
            annotation_ref: mockRef,
            spans_start: [0],
            spans_end: [mention.length - 1],
            mention,
          },
        }),
      ];

      const textSpans = htmlToTextSpans({
        editableDiv: div,
        prevTextSpans,
      });

      expect(textSpans).toEqual([
        {
          ...prevTextSpans[0],
          data: {
            ...prevTextSpans[0].data,
            spans_end: [newMention.length - 1],
            mention: newMention,
          },
        },
      ]);
    });
    it("should include the change of content in the text spans array - if some text was added to a span", () => {
      const div = document.createElement("div");

      const newMention = "Hello World 2";
      div.innerHTML = `<span data-id='span-1'>${newMention}</span>`;

      const mention = "Hello World";
      const prevTextSpans = [
        createMockTextSpan({
          id: "span-1",
          data: {
            annotation_ref: mockRef,
            spans_start: [0],
            spans_end: [mention.length - 1],
            mention,
          },
        }),
      ];

      const textSpans = htmlToTextSpans({
        editableDiv: div,
        prevTextSpans,
      });

      expect(textSpans).toEqual([
        {
          ...prevTextSpans[0],
          data: {
            ...prevTextSpans[0].data,
            spans_end: [newMention.length - 1],
            mention: newMention,
          },
        },
      ]);
    });
    it("should include the change of content in the text spans array - if the modification is made after a span", () => {
      const div = document.createElement("div");

      const newMention = "Hello World";
      const addedContent = " after";
      div.innerHTML = `<span data-id='span-1'>${newMention}</span>${addedContent}`;

      const mention = "Hello";
      const prevTextSpans = [
        createMockTextSpan({
          id: "span-1",
          data: {
            annotation_ref: mockRef,
            spans_start: [0],
            spans_end: [mention.length - 1],
            mention,
          },
        }),
      ];

      const textSpans = htmlToTextSpans({
        editableDiv: div,
        prevTextSpans,
      });

      expect(textSpans).toEqual([
        {
          ...prevTextSpans[0],
          data: {
            ...prevTextSpans[0].data,
            spans_end: [newMention.length - 1],
            mention: newMention,
          },
        },
      ]);
    });
    it("should include the change of content in the text spans array - if the modification is made before a span", () => {
      const div = document.createElement("div");

      const mention = "Hello World";
      const addedContent = "Before ";
      div.innerHTML = `${addedContent}<span data-id='span-1'>${mention}</span>`;

      const prevTextSpans = [
        createMockTextSpan({
          id: "span-1",
          data: {
            annotation_ref: mockRef,
            spans_start: [0],
            spans_end: [mention.length - 1],
            mention,
          },
        }),
      ];

      const textSpans = htmlToTextSpans({
        editableDiv: div,
        prevTextSpans,
      });

      expect(textSpans).toEqual([
        {
          ...prevTextSpans[0],
          data: {
            ...prevTextSpans[0].data,
            spans_start: [addedContent.length],
            spans_end: [mention.length + addedContent.length - 1],
          },
        },
      ]);
    });
  });

  describe("with message content modification and two spans", () => {
    it("should include the change of content in the text spans array - if some text was removed from a span", () => {
      const div = document.createElement("div");

      const newMentionSpan1 = "Hello World";
      const mentionSpan2 = "World";
      div.innerHTML = `<span data-id='span-1'>${newMentionSpan1}</span><span data-id='span-2'>${mentionSpan2}</span>`;

      const mentionSpan1 = "Hello";
      const prevTextSpans = [
        createMockTextSpan({
          id: "span-1",
          data: {
            annotation_ref: mockRef,
            spans_start: [0],
            spans_end: [mentionSpan1.length - 1],
            mention: mentionSpan1,
          },
        }),
        createMockTextSpan({
          id: "span-2",
          data: {
            annotation_ref: mockRef,
            spans_start: [mentionSpan1.length],
            spans_end: [mentionSpan1.length + mentionSpan2.length - 1],
            mention: mentionSpan2,
          },
        }),
      ];

      const textSpans = htmlToTextSpans({
        editableDiv: div,
        prevTextSpans,
      });

      expect(textSpans).toEqual([
        {
          ...prevTextSpans[0],
          data: {
            ...prevTextSpans[0].data,
            spans_end: [newMentionSpan1.length - 1],
            mention: newMentionSpan1,
          },
        },
        {
          ...prevTextSpans[1],
          data: {
            ...prevTextSpans[1].data,
            spans_start: [newMentionSpan1.length],
            spans_end: [newMentionSpan1.length + mentionSpan2.length - 1],
            mention: mentionSpan2,
          },
        },
      ]);
    });
    it("should include the change of content in the text spans array - if some text was added to a span", () => {
      const div = document.createElement("div");

      const newMentionSpan1 = "Hello World 2";
      const mentionSpan2 = "World";
      div.innerHTML = `<span data-id='span-1'>${newMentionSpan1}</span><span data-id='span-2'>${mentionSpan2}</span>`;

      const mentionSpan1 = "Hello";
      const prevTextSpans = [
        createMockTextSpan({
          id: "span-1",
          data: {
            annotation_ref: mockRef,
            spans_start: [0],
            spans_end: [mentionSpan1.length - 1],
            mention: mentionSpan1,
          },
        }),
        createMockTextSpan({
          id: "span-2",
          data: {
            annotation_ref: mockRef,
            spans_start: [mentionSpan1.length],
            spans_end: [mentionSpan1.length + mentionSpan2.length - 1],
            mention: mentionSpan2,
          },
        }),
      ];

      const textSpans = htmlToTextSpans({
        editableDiv: div,
        prevTextSpans,
      });

      expect(textSpans).toEqual([
        {
          ...prevTextSpans[0],
          data: {
            ...prevTextSpans[0].data,
            spans_end: [newMentionSpan1.length - 1],
            mention: newMentionSpan1,
          },
        },
        {
          ...prevTextSpans[1],
          data: {
            ...prevTextSpans[1].data,
            spans_start: [newMentionSpan1.length],
            spans_end: [newMentionSpan1.length + mentionSpan2.length - 1],
            mention: mentionSpan2,
          },
        },
      ]);
    });
    it("should include the change of content in the text spans array - if the modification is made after both spans", () => {
      const div = document.createElement("div");

      const mentionSpan1 = "Hello World";
      const mentionSpan2 = "World";
      const addedContent = " after";
      div.innerHTML = `<span data-id='span-1'>${mentionSpan1}</span><span data-id='span-2'>${mentionSpan2}</span>${addedContent}`;

      const prevTextSpans = [
        createMockTextSpan({
          id: "span-1",
          data: {
            annotation_ref: mockRef,
            spans_start: [0],
            spans_end: [mentionSpan1.length - 1],
            mention: mentionSpan1,
          },
        }),
        createMockTextSpan({
          id: "span-2",
          data: {
            annotation_ref: mockRef,
            spans_start: [mentionSpan1.length],
            spans_end: [mentionSpan1.length + mentionSpan2.length - 1],
            mention: mentionSpan2,
          },
        }),
      ];

      const textSpans = htmlToTextSpans({
        editableDiv: div,
        prevTextSpans,
      });

      expect(textSpans).toEqual([
        {
          ...prevTextSpans[0],
          data: {
            ...prevTextSpans[0].data,
            spans_end: [mentionSpan1.length - 1],
            mention: mentionSpan1,
          },
        },
        {
          ...prevTextSpans[1],
          data: {
            ...prevTextSpans[1].data,
            spans_start: [mentionSpan1.length],
            spans_end: [mentionSpan1.length + mentionSpan2.length - 1],
            mention: mentionSpan2,
          },
        },
      ]);
    });
    it("should include the change of content in the text spans array - if the modification is made before both spans", () => {
      const div = document.createElement("div");

      const mentionSpan1 = "Hello World";
      const mentionSpan2 = "World";
      const addedContent = "Before ";
      div.innerHTML = `${addedContent}<span data-id='span-1'>${mentionSpan1}</span><span data-id='span-2'>${mentionSpan2}</span>`;

      const prevTextSpans = [
        createMockTextSpan({
          id: "span-1",
          data: {
            annotation_ref: mockRef,
            spans_start: [0],
            spans_end: [mentionSpan1.length - 1],
            mention: mentionSpan1,
          },
        }),
        createMockTextSpan({
          id: "span-2",
          data: {
            annotation_ref: mockRef,
            spans_start: [mentionSpan1.length],
            spans_end: [mentionSpan1.length + mentionSpan2.length - 1],
            mention: mentionSpan2,
          },
        }),
      ];

      const textSpans = htmlToTextSpans({
        editableDiv: div,
        prevTextSpans,
      });

      expect(textSpans).toEqual([
        {
          ...prevTextSpans[0],
          data: {
            ...prevTextSpans[0].data,
            spans_start: [addedContent.length],
            spans_end: [addedContent.length + mentionSpan1.length - 1],
            mention: mentionSpan1,
          },
        },
        {
          ...prevTextSpans[1],
          data: {
            ...prevTextSpans[1].data,
            spans_start: [mentionSpan1.length + addedContent.length],
            spans_end: [mentionSpan1.length + addedContent.length + mentionSpan2.length - 1],
            mention: mentionSpan2,
          },
        },
      ]);
    });
  });
});
