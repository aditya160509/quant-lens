import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls";

export default function AnomalyGravityWell({ ticker }) {
  const mountRef = useRef(null);
  const [events, setEvents] = useState([]);
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!ticker) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x000000);

    const width = mountRef.current.clientWidth || 800;
    const height = 600;

    const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
    camera.position.set(0, 40, 40);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(window.devicePixelRatio);
    mountRef.current.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    // Gravity grid
    const gridSize = 60;
    const geometry = new THREE.PlaneGeometry(gridSize, gridSize, 40, 40);
    
    // Fetch data
    fetch(`/api/ml/v2/anomalies/${ticker}`)
      .then((res) => res.json())
      .then((resp) => {
        if (resp.error) throw new Error(resp.error);
        setData(resp);
        setEvents(resp.historical_events || []);

        const vertices = geometry.attributes.position.array;
        
        // Deform grid based on anomaly strength
        for (let i = 0; i < vertices.length; i += 3) {
          const x = vertices[i];
          const y = vertices[i + 1];
          const dist = Math.sqrt(x * x + y * y);
          
          if (resp.is_anomaly) {
            // Create "well" depth
            const depth = (-resp.current_suspicion / 8) * Math.exp(-dist / 12);
            vertices[i + 2] = depth;
          } else {
            // Subtle ripples for normal state
            vertices[i + 2] = Math.sin(dist * 0.5) * 0.5;
          }
        }

        geometry.attributes.position.needsUpdate = true;
        geometry.computeVertexNormals();

        const material = new THREE.MeshBasicMaterial({
          color: resp.is_anomaly ? 0xff3333 : 0x00ffaa,
          wireframe: true,
          transparent: true,
          opacity: 0.4
        });

        const mesh = new THREE.Mesh(geometry, material);
        mesh.rotation.x = -Math.PI / 2;
        scene.add(mesh);

        // Add anomaly pulse stars
        resp.historical_events.slice(-10).forEach((evt, idx) => {
          const star = new THREE.Mesh(
            new THREE.SphereGeometry(0.5, 8, 8),
            new THREE.MeshBasicMaterial({ 
                color: 0xff0000,
                emissive: 0xff0000,
                emissiveIntensity: 1
            })
          );
          star.position.set(
            (Math.random() - 0.5) * 40,
            2,
            (Math.random() - 0.5) * 40
          );
          scene.add(star);
        });
      })
      .catch(err => console.error("Anomaly fetch error:", err));

    let frameId;
    const animate = () => {
      frameId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(frameId);
      if (mountRef.current && renderer.domElement) {
        mountRef.current.removeChild(renderer.domElement);
      }
      renderer.dispose();
    };
  }, [ticker]);

  return (
    <div className="relative w-full bg-black/50 rounded-xl border border-red-500/20 overflow-hidden">
      <div ref={mountRef} className="w-full h-[600px]" />
      
      {data && (
        <div className="absolute top-6 right-6 p-4 bg-black/80 border border-red-500/40 rounded-lg backdrop-blur-md max-w-xs">
          <h4 className="text-red-500 font-mono text-sm border-b border-red-500/20 pb-2 mb-2">GRAVITY WELL DIAGNOSTICS</h4>
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-white/60 text-xs uppercase">Suspicion Score</span>
              <span className="text-red-400 font-bold">{data.current_suspicion.toFixed(1)}%</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-white/60 text-xs uppercase">Status</span>
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${data.is_anomaly ? 'bg-red-500 text-white' : 'bg-green-500/20 text-green-400'}`}>
                {data.is_anomaly ? 'ANOMALY DETECTED' : 'SYSTEM NOMINAL'}
              </span>
            </div>
          </div>
        </div>
      )}

      <div className="absolute bottom-6 left-6 right-6 max-h-40 overflow-y-auto scrollbar-thin scrollbar-thumb-red-500/40">
        <table className="w-full text-left font-mono text-[10px] text-white/80">
          <thead className="bg-red-500/20 text-red-400 sticky top-0">
            <tr>
              <th className="p-2">TIMESTAMP</th>
              <th className="p-2 text-right">SCORE</th>
              <th className="p-2 text-right">VOL SPIKE</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {events.map((e, i) => (
              <tr key={i} className="hover:bg-red-500/5">
                <td className="p-2">{e.date}</td>
                <td className="p-2 text-right text-red-400">{e.suspicion.toFixed(1)}%</td>
                <td className="p-2 text-right">{e.volume_spike.toFixed(2)}x</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
