/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import Scrollbar from "./scroll-area-scrollbar.svelte";
import Thumb from "./scroll-area-thumb.svelte";
import Viewport from "./scroll-area-viewport.svelte";
import Root from "./scroll-area.svelte";

export {
  Root,
  Viewport,
  Scrollbar,
  Thumb,
  //
  Root as ScrollArea,
  Viewport as ScrollAreaViewport,
  Scrollbar as ScrollAreaScrollbar,
  Thumb as ScrollAreaThumb,
};
