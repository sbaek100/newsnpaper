import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";

// design-system §6 상한을 넘지 않는다.
const NODES = 40;        // 노드 40개 이하
const MAX_EDGE = 80;     // 엣지 80개 이하
const POINT_RATIO = 0.15; // 포인트색 15% 이하
const TILT = (4 * Math.PI) / 180; // 카메라 진폭 ±4°
const LERP = 0.05;
const SPIN = 0.05;       // rad/s 이하

function Topology() {
  const group = useRef();
  const { pointer } = useThree();

  const { positions, colors, edges } = useMemo(() => {
    const pos = [];
    for (let i = 0; i < NODES; i++) {
      pos.push(new THREE.Vector3(
        (Math.random() - 0.5) * 9,
        (Math.random() - 0.5) * 4.5,
        (Math.random() - 0.5) * 4,
      ));
    }
    const grey = new THREE.Color("#D1D6DB");
    const point = new THREE.Color("#3182F6");
    const col = new Float32Array(NODES * 3);
    pos.forEach((_, i) => {
      (i / NODES < POINT_RATIO ? point : grey).toArray(col, i * 3);
    });

    const ed = [];
    for (let i = 0; i < NODES && ed.length < MAX_EDGE * 2; i++) {
      for (let j = i + 1; j < NODES && ed.length < MAX_EDGE * 2; j++) {
        if (pos[i].distanceTo(pos[j]) < 2.2) ed.push(pos[i], pos[j]);
      }
    }
    return {
      positions: new Float32Array(pos.flatMap((v) => [v.x, v.y, v.z])),
      colors: col,
      edges: new Float32Array(ed.flatMap((v) => [v.x, v.y, v.z])),
    };
  }, []);

  useFrame((_, dt) => {
    const g = group.current;
    if (!g) return;
    g.rotation.y += SPIN * dt;                       // 자동 회전
    g.rotation.x += (pointer.y * TILT - g.rotation.x) * LERP;  // 마우스 추종
    g.rotation.z += (-pointer.x * TILT - g.rotation.z) * LERP;
  });

  return (
    <group ref={group}>
      <lineSegments>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[edges, 3]} />
        </bufferGeometry>
        <lineBasicMaterial color="#D1D6DB" transparent opacity={0.55} />
      </lineSegments>
      <points>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[positions, 3]} />
          <bufferAttribute attach="attributes-color" args={[colors, 3]} />
        </bufferGeometry>
        <pointsMaterial size={0.11} vertexColors sizeAttenuation />
      </points>
    </group>
  );
}

export default function Scene() {
  return (
    <Canvas
      camera={{ position: [0, 0, 8], fov: 50 }}
      dpr={[1, 1.5]}                 // DPR 상한 1.5
      gl={{ alpha: true, antialias: true }}
      style={{ background: "transparent" }}  // 흰 배경이 그대로 비친다
    >
      <Topology />
    </Canvas>
  );
}
