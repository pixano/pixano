/**
 *
 * Function to wrap the selected text in a custom tag with metadata
 *
 */
export function tagSelectedText({
  selection,
  range,
  selectedText,
  tagName = "span",
  metadata = {},
  className = undefined,
}: {
  selection: Selection;
  range: Range;
  selectedText: string;
  tagName?: string;
  metadata?: Record<string, string>;
  className?: string;
}) {
  // Create a custom element with metadata
  const customTag = document.createElement(tagName);
  Object.keys(metadata).forEach((key) => {
    customTag.setAttribute(`data-${key}`, metadata[key]); // Add metadata as data attributes
  });

  if (className) {
    const classList = className.split(" ");
    customTag.classList.add(...classList);
  }

  // Wrap the selected text in the custom tag
  range.deleteContents(); // Remove selected text from the DOM
  range.insertNode(customTag); // Insert custom tag in the place of the selected text
  customTag.textContent = selectedText; // Set the text inside the custom tag

  // Clear the selection
  selection.removeAllRanges();
}
