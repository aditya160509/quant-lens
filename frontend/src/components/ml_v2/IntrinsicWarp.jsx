import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls";

export default function IntrinsicWarp({ ticker }) {
  const mountRef = useRef(null);
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!ticker) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0a14);

    const width = mountRef.current.clientWidth || 800;
    const height = 600;

    const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
    camera.position.set(50, 80, 50);

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
    pointLight.position.set(50, 100, 50);
    scene.add(pointLight);

    fetch(`/api/ml/v2/valuation/${ticker}`)
      .then((res) => res.json())
      .then((resp) => {
        if (resp.error) throw new Error(resp.error);
        setData(resp);

        // Surface Grid
        const grid = resp.surface_grid;
        const geometry = new THREE.PlaneGeometry(100, 100, 29, 29);
        const vertices = geometry.attributes.position.array;

        // Map height
        const vals = grid.values.flat();
        const maxV = Math.max(...vals);
        const minV = Math.min(...vals);

        for (let i = 0; i < 30; i++) {
          for (let j = 0; j < 30; j++) {
            const idx = (i * 30 + j) * 3;
            const val = grid.values[i][j];
            vertices[idx + 2] = ((val - minV) / (maxV - minV)) * 50;
          }
        }

        geometry.attributes.position.needsUpdate = true;
        geometry.computeVertexNormals();

        const material = new THREE.MeshPhongMaterial({
          color: 0x00ff88,
          emissive: 0x00ff88,
          emissiveIntensity: 0.1,
          side: THREE.DoubleSide,
          transparent: true,
          opacity: 0.8,
          wireframe: true
        });

        const mesh = new THREE.Mesh(geometry, material);
        mesh.rotation.x = -Math.PI / 2;
        scene.add(mesh);

        // Markers
        const addMarker = (val, color) => {
            const h = ((val - minV) / (maxV - minV)) * 50;
            const s = new THREE.Mesh(
                new THREE.SphereGeometry(2, 16, 16),
                new THREE.MeshBasicMaterial({ color, emissive: color })
            );
            s.position.set(0, h, 0);
            scene.add(s);
        };

        addMarker(resp.current_price, 0xff0000); // Current
        addMarker(resp.median_value, 0x00ff00); // Fair
      })
      .catch(err => console.error("Valuation fetch error:", err));

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
    <div className="relative w-full bg-black/50 rounded-xl border border- терминал-cyan/20 overflow-hidden">
      <div ref={mountRef} className="w-full h-[600px]" />
      
      {data && (
        <div className="absolute top-10 left-10 flex gap-8">
            <div className="p-6 bg-black/90 border border-green-500/30 rounded-xl backdrop-blur-xl w-64">
                <h3 className="text-green-400 font-bold mb-4 uppercase tracking-tighter">Intrinsic Analysis</h3>
                <div className="space-y-4 font-mono">
                    <div className="flex justify-between items-end">
                        <span className="text-white/40 text-[10px]">CURRENT</span>
                        <span className="text-red-400 text-lg">${data.current_price.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between items-end">
                        <span className="text-white/40 text-[10px]">FAIR VALUE</span>
                        <span className="text-green-400 text-lg">${data.median_value.toFixed(2)}</span>
                    </div>
                    <div className="pt-2 border-t border-white/10">
                        <div className="text-[10px] text-white/40 mb-1 uppercase text-center">Implied Upside</div>
                        <div className={`text-2xl font-bold text-center ${data.upside > 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {data.upside > 0 ? '+' : ''}{data.upside.toFixed(1)}%
                        </div>
                    </div>
                </div>
            </div>

            <div className="p-6 bg-black/90 border border-cyan-500/30 rounded-xl backdrop-blur-xl w-64">
                <h3 className="text-cyan-400 font-bold mb-4 uppercase tracking-tighter">Margin of Safety</h3>
                <div className="space-y-3">
                    {Object.entries(data.margin_of_safety).map(([k, v]) => (
                        <div key={k} className="flex justify-between items-center text-[10px] font-mono">
                            <span className="text-white/40 uppercase">{k.replace(/_/g, ' ')}</span>
                            <span className="text-cyan-300">{typeof v === 'number' ? v.toFixed(2) : v}</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
      )}
    </div>
  );
}
