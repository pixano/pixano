/**
 *
 * Function to wrap the selected text in a custom tag with metadata
 *
 */
export function tagSelectedText({
  tagName = "span",
  metadata = {},
  className = undefined,
}: {
  tagName?: string;
  metadata?: Record<string, string>;
  className?: string;
}) {
  const selection = window.getSelection();

  if (selection.rangeCount === 0) {
    alert("Please select some text to tag.");
    return;
  }

  const range = selection.getRangeAt(0); // Get selected range
  const selectedText = selection.toString();

  if (!selectedText) {
    alert("Please select some text to tag.");
    return;
  }

  // Create a custom element with metadata
  const customTag = document.createElement(tagName);
  Object.keys(metadata).forEach((key) => {
    customTag.setAttribute(`data-${key}`, metadata[key]); // Add metadata as data attributes
  });

  if (className) {
    customTag.classList.add(className);
  }

  // Wrap the selected text in the custom tag
  range.deleteContents(); // Remove selected text from the DOM
  range.insertNode(customTag); // Insert custom tag in the place of the selected text
  customTag.textContent = selectedText; // Set the text inside the custom tag

  // Clear the selection
  selection.removeAllRanges();
}
