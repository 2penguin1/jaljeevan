import { Line, useTexture } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Bloom, EffectComposer } from "@react-three/postprocessing";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import type { Hazard } from "@/lib/api/types";
import { HAZARDS } from "@/lib/hazards";
import { DISPLACEMENT, PLANE, project, textureUV } from "./projection";

export type Ember = { id: string; lon: number; lat: number; hazard: Hazard; active: boolean; score: number };

export type SceneProps = {
  embers: Ember[];
  hotspot: { lon: number; lat: number } | null;
  motion: boolean; // false: still camera, no pulsing (reduced motion)
  lite: boolean; // phones / low-end: lighter mesh, no bloom
  onReady?: () => void;
};

const RIVER = new THREE.Color(...HAZARDS.flood.rgb.map((c) => c / 255) as [number, number, number]);

type HeightSampler = (lon: number, lat: number) => number;

/** Reads the baked height image once so rivers and embers can sit on the surface. */
function useHeightSampler(image: HTMLImageElement | undefined): HeightSampler {
  return useMemo(() => {
    if (!image?.width) return () => 0;
    const c = document.createElement("canvas");
    c.width = image.width;
    c.height = image.height;
    const ctx = c.getContext("2d", { willReadFrequently: true });
    if (!ctx) return () => 0;
    ctx.drawImage(image, 0, 0);
    const { data, width, height } = ctx.getImageData(0, 0, c.width, c.height);
    return (lon, lat) => {
      const [u, v] = textureUV(lon, lat);
      const x = Math.min(width - 1, Math.max(0, Math.round(u * (width - 1))));
      const y = Math.min(height - 1, Math.max(0, Math.round(v * (height - 1))));
      return (data[(y * width + x) * 4] / 255) * DISPLACEMENT;
    };
  }, [image]);
}

function Relief({ segments, onHeights }: { segments: number; onHeights: (s: HeightSampler) => void }) {
  const [albedo, normal, height] = useTexture(["/landing/albedo.webp", "/landing/normal.webp", "/landing/height.png"]);
  const gl = useThree((s) => s.gl);
  useMemo(() => {
    albedo.colorSpace = THREE.SRGBColorSpace;
    for (const t of [albedo, normal, height]) t.anisotropy = Math.min(8, gl.capabilities.getMaxAnisotropy());
  }, [albedo, normal, height, gl]);
  const sampler = useHeightSampler(height.image as HTMLImageElement);
  useEffect(() => onHeights(sampler), [sampler, onHeights]);
  return (
    <mesh rotation-x={-Math.PI / 2} receiveShadow>
      <planeGeometry args={[PLANE.w, PLANE.h, segments, segments]} />
      <meshStandardMaterial map={albedo} normalMap={normal} displacementMap={height} displacementScale={DISPLACEMENT}
        alphaTest={0.5} roughness={0.93} metalness={0} />
    </mesh>
  );
}

function Rivers({ heightAt }: { heightAt: HeightSampler }) {
  const [lines, setLines] = useState<[number, number][][]>([]);
  useEffect(() => {
    fetch("/landing/rivers.json").then((r) => r.json()).then(setLines).catch(() => setLines([]));
  }, []);
  const points = useMemo(
    () => lines.map((line) => line.map(([lon, lat]) => {
      const [x, z] = project(lon, lat);
      return new THREE.Vector3(x, heightAt(lon, lat) + 0.002, z);
    })),
    [lines, heightAt],
  );
  return points.map((pts, i) => (
    <Line key={i} points={pts} color={RIVER}
      lineWidth={1} transparent opacity={0.55} toneMapped={false} />
  ));
}

function Embers({ embers, heightAt, motion }: { embers: Ember[]; heightAt: HeightSampler; motion: boolean }) {
  const group = useRef<THREE.Group>(null);
  useFrame(({ clock }) => {
    if (!motion || !group.current) return;
    group.current.children.forEach((child, i) => {
      const e = embers[i];
      if (!e?.active) return;
      const s = 1 + 0.35 * Math.sin(clock.elapsedTime * 2.4 + i);
      child.scale.setScalar(s);
    });
  });
  return (
    <group ref={group}>
      {embers.map((e) => {
        const [x, z] = project(e.lon, e.lat);
        const [r, g, b] = HAZARDS[e.hazard].rgb;
        const glow = e.active ? 6 : 1.6; // >1 drives the bloom
        const color = new THREE.Color(r / 255, g / 255, b / 255).multiplyScalar(glow);
        const radius = (e.active ? 0.0075 : 0.0045) * (0.7 + e.score / 160);
        return (
          <mesh key={e.id} position={[x, heightAt(e.lon, e.lat) + radius, z]}>
            <sphereGeometry args={[radius, 16, 16]} />
            <meshBasicMaterial color={color} toneMapped={false} transparent opacity={e.active ? 1 : 0.7} />
          </mesh>
        );
      })}
    </group>
  );
}

const smooth = (t: number) => t * t * (3 - 2 * t);

/** Three scroll beats: the whole country -> the worst hotspot -> a low look across the horizon. */
function CameraRig({ hotspot, motion }: { hotspot: SceneProps["hotspot"]; motion: boolean }) {
  const { camera, size } = useThree();
  const look = useRef(new THREE.Vector3());
  const beats = useMemo(() => {
    const portrait = size.width < size.height;
    const far = portrait ? 1.9 : 1;
    const [hx, hz] = hotspot ? project(hotspot.lon, hotspot.lat) : [0, 0.2];
    // landscape: India sits right of the headline, so the camera looks a little left of centre
    // portrait: look north of centre so India sits in the lower half, under the headline
    const overviewTarget = new THREE.Vector3(portrait ? 0.05 : -0.42, 0, portrait ? -0.62 : 0.04);
    return [
      { pos: new THREE.Vector3(overviewTarget.x + 0.05, 2.15 * far, overviewTarget.z + 1.25 * far), target: overviewTarget },
      { pos: new THREE.Vector3(hx + 0.18, 0.5 * far, hz + 0.62 * far), target: new THREE.Vector3(hx, 0, hz) },
      { pos: new THREE.Vector3(0.12, 0.34, 1.3 * far), target: new THREE.Vector3(0, -0.02, -0.05) },
    ];
  }, [hotspot, size.width, size.height]);

  useFrame((_, delta) => {
    const max = document.documentElement.scrollHeight - window.innerHeight;
    const p = motion && max > 0 ? Math.min(1, Math.max(0, window.scrollY / max)) : 0;
    const seg = p < 0.5 ? 0 : 1;
    const t = smooth(seg === 0 ? p / 0.5 : (p - 0.5) / 0.5);
    const a = beats[seg], b = beats[seg + 1];
    const pos = a.pos.clone().lerp(b.pos, t);
    const target = a.target.clone().lerp(b.target, t);
    const k = motion ? 1 - Math.exp(-delta * 4) : 1; // ease toward the scroll position
    camera.position.lerp(pos, k);
    look.current.lerp(target, k);
    camera.lookAt(look.current);
  });
  return null;
}

export default function Scene({ embers, hotspot, motion, lite, onReady }: SceneProps) {
  const [heightAt, setHeightAt] = useState<HeightSampler>(() => () => 0);
  const onHeights = useMemo(() => (s: HeightSampler) => setHeightAt(() => s), []);
  return (
    <Canvas
      dpr={lite ? [1, 1.5] : [1, 2]}
      camera={{ fov: 32, near: 0.01, far: 20, position: [-0.37, 2.15, 1.29] }}
      gl={{ antialias: !lite, powerPreference: "high-performance" }}
      onCreated={({ gl, scene }) => {
        gl.toneMapping = THREE.ACESFilmicToneMapping;
        scene.background = new THREE.Color("#0b0a09");
        scene.fog = new THREE.Fog("#0b0a09", 4.2, 9); // only the far horizon fades, at any camera distance
      }}
    >
      <ambientLight intensity={0.22} />
      <hemisphereLight args={["#c9d8e0", "#1b1916", 0.25]} />
      {/* low, warm key light from the north-west rakes across the relief like late sun */}
      <directionalLight position={[-2.2, 1.1, -1.6]} intensity={2.6} color="#ffe0b8" />
      <directionalLight position={[2, 1.4, 2]} intensity={0.35} color="#9fbfd0" />
      <Relief segments={lite ? 256 : 512} onHeights={onHeights} />
      <Rivers heightAt={heightAt} />
      <Embers embers={embers} heightAt={heightAt} motion={motion} />
      <CameraRig hotspot={hotspot} motion={motion} />
      <Ready onReady={onReady} />
      {!lite && (
        <EffectComposer>
          <Bloom mipmapBlur intensity={1.1} luminanceThreshold={0.62} luminanceSmoothing={0.2} />
        </EffectComposer>
      )}
    </Canvas>
  );
}

/** Fires once the first frame with textures has rendered, so the page can fade the canvas in over the poster. */
function Ready({ onReady }: { onReady?: () => void }) {
  const done = useRef(false);
  useFrame(() => {
    if (!done.current) {
      done.current = true;
      requestAnimationFrame(() => onReady?.());
    }
  });
  return null;
}
