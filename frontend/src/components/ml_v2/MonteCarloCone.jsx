import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";

export default function MonteCarloCone({ ticker }) {
  const mountRef = useRef(null);
  const [stats, setStats] = useState(null);

  useEffect(() => {
    if (!ticker) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0014);

    const width = mountRef.current.clientWidth || 800;
    const height = 600;

    const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
    camera.position.set(60, 40, 60);
    camera.lookAt(15, 0, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(window.devicePixelRatio);
    mountRef.current.appendChild(renderer.domElement);

    // Floor Grid
    const grid = new THREE.GridHelper(200, 20, 0x444444, 0x222222);
    grid.position.y = -20;
    scene.add(grid);

    fetch(`/api/ml/v2/montecarlo/${ticker}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.error) throw new Error(data.error);
        setStats(data);

        // Draw sample paths
        data.paths.forEach((path, idx) => {
          const points = path.map((price, day) => 
            new THREE.Vector3(day, (price - 100) * 1.5, (idx - 50) * 0.2)
          );
          const geometry = new THREE.BufferGeometry().setFromPoints(points);
          const material = new THREE.LineBasicMaterial({ 
            color: 0x00ffaa,
            transparent: true,
            opacity: 0.1
          });
          const line = new THREE.Line(geometry, material);
          scene.add(line);
        });

        // Probability cloud (Envelope)
        const envelopeShape = new THREE.CylinderGeometry(
            (data.percentiles.p95 - 100) * 1.5, 
            0, 
            30, 
            32, 
            1, 
            true
        );
        const envMaterial = new THREE.MeshBasicMaterial({
            color: 0x0088ff,
            transparent: true,
            opacity: 0.1,
            wireframe: true,
            side: THREE.DoubleSide
        });
        const cone = new THREE.Mesh(envelopeShape, envMaterial);
        cone.rotation.z = -Math.PI / 2;
        cone.position.set(15, 0, 0);
        scene.add(cone);
      })
      .catch(err => console.error("MC fetch error:", err));

    let frameId;
    const animate = () => {
      frameId = requestAnimationFrame(animate);
      camera.position.x = 60 * Math.cos(Date.now() * 0.0003);
      camera.position.z = 60 * Math.sin(Date.now() * 0.0003);
      camera.lookAt(15, 0, 0);
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
    <div className="relative w-full bg-black/50 rounded-xl border border-blue-500/20 overflow-hidden">
      <div ref={mountRef} className="w-full h-[600px]" />
      
      {stats && (
        <div className="absolute top-6 left-6 p-4 bg-black/80 border border-blue-400/30 rounded-lg backdrop-blur-md">
           <h3 className="text-blue-400 font-mono text-sm uppercase mb-3 tracking-widest">Monte Carlo Hologram</h3>
           <div className="grid grid-cols-2 gap-x-8 gap-y-2">
                <div className="flex flex-col">
                    <span className="text-white/40 text-[10px] uppercase">Probability Profit</span>
                    <span className="text-green-400 text-lg font-bold">{stats.prob_profit.toFixed(1)}%</span>
                </div>
                <div className="flex flex-col">
                    <span className="text-white/40 text-[10px] uppercase">Median Terminal</span>
                    <span className="text-white text-lg font-bold">${stats.percentiles.p50.toFixed(2)}</span>
                </div>
                <div className="flex flex-col col-span-2 mt-2 pt-2 border-t border-white/10">
                    <span className="text-white/40 text-[10px] uppercase mb-1">90% Confidence Interval</span>
                    <div className="flex justify-between font-mono text-xs text-blue-300">
                        <span>Low: ${stats.percentiles.p5.toFixed(2)}</span>
                        <span>High: ${stats.percentiles.p95.toFixed(2)}</span>
                    </div>
                </div>
           </div>
        </div>
      )}

      <div className="absolute bottom-6 right-6 pointer-events-none text-right">
        <p className="text-blue-400/60 text-[10px] font-mono">GARCH(1,1) HYPER-PROJECTION: 50,000 PATHS GENERATED</p>
      </div>
    </div>
  );
}
