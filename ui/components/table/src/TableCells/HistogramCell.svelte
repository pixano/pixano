<script lang="ts">
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
  import { Histogram } from "@pixano/core";

  import type { DatasetStat } from "@pixano/core";

  // Exports
  export let value: DatasetStat;
</script>

<div class="mx-8 h-24">
  <Histogram hist={value} minimal={true} />
</div>
