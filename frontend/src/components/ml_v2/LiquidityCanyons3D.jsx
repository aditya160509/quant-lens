import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls";

export default function LiquidityCanyons3D({ ticker }) {
  const mountRef = useRef(null);
  const [pathAnalysis, setPathAnalysis] = useState(null);

  useEffect(() => {
    if (!ticker) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x050510);

    const width = mountRef.current.clientWidth || 800;
    const height = 600;

    const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
    camera.position.set(0, 100, 150);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(window.devicePixelRatio);
    mountRef.current.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    // Lighting
    const ambientLight = new THREE.AmbientLight(0x404040);
    scene.add(ambientLight);
    const pointLight = new THREE.PointLight(0xffffff, 1, 300);
    pointLight.position.set(0, 150, 100);
    scene.add(pointLight);

    fetch(`/api/ml/v2/liquidity/${ticker}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.error) throw new Error(data.error);
        setPathAnalysis(data.resistance_path);

        const maxVol = Math.max(...data.volume_profile.map((b) => b.volume));
        const count = data.volume_profile.length;

        data.volume_profile.forEach((bucket, idx) => {
          const h = (bucket.volume / maxVol) * 100;
          const geometry = new THREE.BoxGeometry(2, h, 2);
          
          let color = 0x0088ff;
          if (data.liquidity_voids.some(v => Math.abs(v.price - bucket.price) < 0.1)) color = 0xff3333;
          if (Math.abs(bucket.price - data.poc) < 0.1) color = 0xffff00;
          if (bucket.price >= data.val && bucket.price <= data.vah) color = 0x00ff88;

          const material = new THREE.MeshPhongMaterial({
            color,
            emissive: color,
            emissiveIntensity: 0.2,
            transparent: true,
            opacity: 0.9
          });

          const pillar = new THREE.Mesh(geometry, material);
          pillar.position.set((idx - count / 2) * 3, h / 2, 0);
          scene.add(pillar);
        });
      })
      .catch(err => console.error("Liquidity fetch error:", err));

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
    <div className="relative w-full bg-black/50 rounded-xl border border-green-500/20 overflow-hidden">
      <div ref={mountRef} className="w-full h-[600px]" />
      
      {pathAnalysis && (
        <div className="absolute top-6 left-6 p-6 bg-black/90 border-l-4 border-terminal-green max-w-sm backdrop-blur-xl">
           <h3 className="text-terminal-green font-mono text-sm uppercase mb-2">Path of Least Resistance</h3>
           <p className="text-white/80 text-xs font-mono leading-relaxed mb-4">
            {pathAnalysis.summary}
           </p>
           <div className="grid grid-cols-3 gap-2 text-center text-[10px]">
                <div className="bg-green-500/10 p-2 rounded">
                    <div className="text-green-400 font-bold mb-1">VAL</div>
                    <div className="text-white">${pathAnalysis.key_levels.nearest_support.toFixed(2)}</div>
                </div>
                <div className="bg-yellow-500/10 p-2 rounded">
                    <div className="text-yellow-400 font-bold mb-1">POC</div>
                    <div className="text-white">${pathAnalysis.key_levels.poc.toFixed(2)}</div>
                </div>
                <div className="bg-cyan-500/10 p-2 rounded">
                    <div className="text-cyan-400 font-bold mb-1">VAH</div>
                    <div className="text-white">${pathAnalysis.key_levels.nearest_resistance.toFixed(2)}</div>
                </div>
           </div>
        </div>
      )}

      <div className="absolute bottom-6 right-6 flex items-center gap-4 text-[10px] font-mono">
        <div className="flex items-center gap-1"><div className="w-2 h-2 bg-terminal-green"></div> VALUE AREA</div>
        <div className="flex items-center gap-1"><div className="w-2 h-2 bg-yellow-400"></div> POC</div>
        <div className="flex items-center gap-1"><div className="w-2 h-2 bg-red-500"></div> VOID</div>
      </div>
    </div>
  );
}
