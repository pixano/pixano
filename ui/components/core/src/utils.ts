/**
 * @copyright CEA
 * @author CEA
 * @license CECILL
 *
 * This software is a collaborative computer program whose purpose is to
 * generate and explore labeled data for computer vision applications.
 * This software is governed by the CeCILL-C license under French law and
 * abiding by the rules of distribution of free software. You can use,
 * modify and/ or redistribute the software under the terms of the CeCILL-C
 * license as circulated by CEA, CNRS and INRIA at the following URL
 *
 * http://www.cecill.info
 */

// Imports
import { scaleOrdinal } from "d3";
import { schemeSet3 } from "d3-scale-chromatic";

// Exports
/**
 * Generates an unique color based on a given id.
 * @param id the id
 */
export function getColor(classes) {
  let classes_range = [
    Math.min(...classes.map((cat) => cat.id)),
    Math.max(...classes.map((cat) => cat.id)),
  ];
  return scaleOrdinal(schemeSet3).domain(classes_range);
}
