export const getSelection = () => {
  const selection = window.getSelection();

  if (selection.rangeCount === 0) {
    alert("Please select some text to tag.");
    return;
  }

  return selection;
};
