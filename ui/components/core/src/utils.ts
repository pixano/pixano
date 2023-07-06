/**
@copyright CEA-LIST/DIASI/SIALV/LVA (2023)
@author CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
@license CECILL-C

This software is a collaborative computer program whose purpose is to
generate and explore labeled data for computer vision applications.
This software is governed by the CeCILL-C license under French law and
abiding by the rules of distribution of free software. You can use, 
modify and/ or redistribute the software under the terms of the CeCILL-C
license as circulated by CEA, CNRS and INRIA at the following URL

http://www.cecill.info
*/

import { schemeSet3 } from "d3-scale-chromatic";
import { scaleOrdinal } from "d3";

/**
 * Generates an unique color based on a given id.
 * @param id the id
 */
export function getColor(categories: Array<number>) {
  return scaleOrdinal().domain(categories).range(schemeSet3);
}
