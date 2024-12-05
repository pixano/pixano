export const getSelectedText = (selection: Selection) => {
  const selectedText = selection.toString();

  if (!selectedText) {
    alert("Please select some text to tag.");
    return null;
  }

  return selectedText;
};
