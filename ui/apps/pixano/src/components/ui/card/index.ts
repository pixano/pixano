/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import Content from "./card-content.svelte";
import Description from "./card-description.svelte";
import Footer from "./card-footer.svelte";
import Header from "./card-header.svelte";
import Title from "./card-title.svelte";
import Root from "./card.svelte";

export {
  Root,
  Header,
  Footer,
  Title,
  Content,
  Description,
  //
  Root as Card,
  Header as CardHeader,
  Footer as CardFooter,
  Title as CardTitle,
  Content as CardContent,
  Description as CardDescription,
};
