<script lang="ts">
	import { T } from '@threlte/core';
	import { OrbitControls } from '@threlte/extras';
	import * as THREE from 'three';

	// Generate random point cloud data
	const pointCount = 500;
	const positions = new Float32Array(pointCount * 3);
	const colors = new Float32Array(pointCount * 3);

	for (let i = 0; i < pointCount; i++) {
		const theta = Math.random() * Math.PI * 2;
		const phi = Math.acos(Math.random() * 2 - 1);
		const r = Math.random() * 3 + 0.5;

		positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
		positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
		positions[i * 3 + 2] = r * Math.cos(phi);

		const t = (positions[i * 3 + 1] + 3.5) / 7;
		colors[i * 3] = t;
		colors[i * 3 + 1] = 0.4 + t * 0.4;
		colors[i * 3 + 2] = 1 - t * 0.5;
	}

	const geometry = new THREE.BufferGeometry();
	geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
	geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
</script>

<T.PerspectiveCamera
	makeDefault
	position={[6, 4, 6]}
	oncreate={(ref) => {
		ref.lookAt(0, 0, 0);
	}}
>
	<OrbitControls enableDamping autoRotate autoRotateSpeed={0.5} />
</T.PerspectiveCamera>

<T.DirectionalLight position={[5, 5, 5]} intensity={1} />
<T.AmbientLight intensity={0.4} />

<!-- Point cloud -->
<T.Points>
	<T.BufferGeometry
		oncreate={(ref) => {
			ref.setAttribute('position', new THREE.BufferAttribute(positions, 3));
			ref.setAttribute('color', new THREE.BufferAttribute(colors, 3));
		}}
	/>
	<T.PointsMaterial size={0.08} vertexColors sizeAttenuation />
</T.Points>

<!-- Central reference cube -->
<T.Mesh position.y={0}>
	<T.BoxGeometry args={[0.5, 0.5, 0.5]} />
	<T.MeshStandardMaterial color="#6366f1" wireframe />
</T.Mesh>

<!-- Ground grid -->
<T.GridHelper args={[10, 10, '#333333', '#222222']} position.y={-3.5} />
