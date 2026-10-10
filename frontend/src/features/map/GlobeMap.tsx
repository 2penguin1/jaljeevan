import { MapboxOverlay } from "@deck.gl/mapbox";
import type { Layer } from "@deck.gl/core";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { EmptyState } from "@/components/patterns/EmptyState";
import { usePrefersReducedMotion } from "@/lib/motion";
import { INDIA_BOUNDS, INDIA_CENTER, loadMapStyle } from "./mapStyle";

/** MapLibre globe with deck.gl layers interleaved into its WebGL context. */
export function GlobeMap({ layers, zoneCount }: { layers: Layer[]; zoneCount: number }) {
  const container = useRef<HTMLDivElement>(null);
  const overlay = useRef<MapboxOverlay | null>(null);
  const [failed, setFailed] = useState(false);
  const reduced = usePrefersReducedMotion();
  const latestLayers = useRef(layers);
  latestLayers.current = layers;

  useEffect(() => {
    const abort = new AbortController();
    let map: maplibregl.Map | undefined;
    loadMapStyle(abort.signal)
      .then((style) => {
        if (!container.current) return;
        map = new maplibregl.Map({
          container: container.current,
          style,
          center: INDIA_CENTER,
          zoom: 1.6,
          attributionControl: { compact: true },
          // deck.gl's globe view cannot follow a tilted or rotated camera, so the camera stays flat and north-up
          maxPitch: 0,
          dragRotate: false,
          pitchWithRotate: false,
          touchPitch: false,
        });
        map.touchZoomRotate.disableRotation();
        map.keyboard.disableRotation();
        if (import.meta.env.DEV) (window as unknown as { __map: maplibregl.Map }).__map = map; // debugging aid
        map.once("load", () => {
          // deck reads the projection when added: add it only once the globe style is live, or it draws flat
          overlay.current = new MapboxOverlay({ interleaved: true, layers: latestLayers.current });
          map!.addControl(overlay.current);
          map!.fitBounds(INDIA_BOUNDS, { padding: 48, duration: reduced ? 0 : 2400 });
        });
      })
      .catch((err) => {
        if ((err as Error).name !== "AbortError") setFailed(true); // no WebGL, or the map could not start
      });
    return () => {
      abort.abort();
      overlay.current = null;
      map?.remove();
    };
    // the map is created once; layer updates go through setProps below
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    overlay.current?.setProps({ layers });
  }, [layers]);

  if (failed) {
    return (
      <EmptyState
        className="p-8"
        title="This browser can't draw the 3D map"
        body="Every zone is also listed in a table."
        action={<Link to="/zones" className="rounded-[6px] border hairline px-3 py-2 hover:bg-raised">See all zones</Link>}
      />
    );
  }
  // maplibre's CSS forces position: relative on the map element, so the sizing lives on a wrapper.
  return (
    <div className="absolute inset-0" data-zone-count={zoneCount}>
      <div ref={container} className="h-full w-full" aria-label="Map of India" role="region" />
    </div>
  );
}
