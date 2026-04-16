<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { T } from "@threlte/core";
  import { OrbitControls } from "@threlte/extras";
  import { onMount } from "svelte";
  import * as THREE from "three";

  interface Props {
    pointCloudUrl?: string;
  }

  let { pointCloudUrl }: Props = $props();

  let positions = $state<Float32Array>(new Float32Array(0));
  let colors = $state<Float32Array>(new Float32Array(0));
  let loading = $state(true);

  onMount(async () => {
    if (!pointCloudUrl) {
      loading = false;
      return;
    }
    try {
      const response = await fetch(pointCloudUrl);
      const buffer = await response.arrayBuffer();
      // nuScenes .pcd.bin: 5 float32 per point (x, y, z, intensity, ring_index)
      const floats = new Float32Array(buffer);
      const stride = 5;
      const pointCount = Math.floor(floats.length / stride);

      const pos = new Float32Array(pointCount * 3);
      const col = new Float32Array(pointCount * 3);

      let minZ = Infinity,
        maxZ = -Infinity;
      for (let i = 0; i < pointCount; i++) {
        const z = floats[i * stride + 2];
        if (z < minZ) minZ = z;
        if (z > maxZ) maxZ = z;
      }
      const rangeZ = maxZ - minZ || 1;

      for (let i = 0; i < pointCount; i++) {
        pos[i * 3] = floats[i * stride];
        pos[i * 3 + 1] = floats[i * stride + 2]; // z -> up
        pos[i * 3 + 2] = -floats[i * stride + 1]; // -y -> forward
        // Color by height
        const t = (floats[i * stride + 2] - minZ) / rangeZ;
        col[i * 3] = t;
        col[i * 3 + 1] = 0.4 + t * 0.4;
        col[i * 3 + 2] = 1 - t * 0.5;
      }

      positions = pos;
      colors = col;
    } catch (e) {
      console.error("Failed to load point cloud:", e);
    }
    loading = false;
  });
</script>

<T.PerspectiveCamera
  makeDefault
  position={[30, 20, 30]}
  oncreate={(ref) => {
    ref.lookAt(0, 0, 0);
  }}
>
  <OrbitControls enableDamping />
</T.PerspectiveCamera>

<T.AmbientLight intensity={0.6} />

{#if !loading && positions.length > 0}
  <T.Points>
    <T.BufferGeometry
      oncreate={(ref) => {
        ref.setAttribute("position", new THREE.BufferAttribute(positions, 3));
        ref.setAttribute("color", new THREE.BufferAttribute(colors, 3));
      }}
    />
    <T.PointsMaterial size={0.05} vertexColors sizeAttenuation />
  </T.Points>
{/if}

<T.GridHelper args={[100, 50, "#333333", "#222222"]} />
