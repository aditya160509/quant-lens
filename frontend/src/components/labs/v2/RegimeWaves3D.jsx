import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls";
import { fetchML2Regime } from "@/lib/api";

export default function RegimeWaves3D({ universe, ticker }) {
  const mountRef = useRef(null);
  const sceneRef = useRef(null);
  const [regimeData, setRegimeData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let animationFrameId;
    let isMounted = true;
    const mountNode = mountRef.current;
    if (!mountNode) return;

    const width = mountNode.clientWidth || 800;
    const height = mountNode.clientHeight || 600;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0a0f);

    const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
    camera.position.set(0, 0, 50);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    mountNode.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    let currentMesh = null;
    let currentGeom = null;
    let currentMat = null;

    const createSpectralMesh = (energyData) => {
      const geometry = new THREE.PlaneGeometry(80, 80, 50, 50);
      const vertices = geometry.attributes.position.array;
      for (let i = 0; i < vertices.length; i += 3) {
        const x = vertices[i], y = vertices[i + 1];
        const freq = Math.sqrt(x * x + y * y) / 10;
        const hVal = (energyData.trend || 1) * Math.sin(freq * 0.5) + (energyData.swing || 1) * Math.sin(freq * 2) + (energyData.noise || 1) * Math.sin(freq * 5);
        vertices[i + 2] = hVal * 0.01;
      }
      geometry.attributes.position.needsUpdate = true;
      geometry.computeVertexNormals();
      const material = new THREE.MeshPhongMaterial({ color: 0x00ff88, wireframe: true, emissive: 0x00ff88, emissiveIntensity: 0.2 });
      return { mesh: new THREE.Mesh(geometry, material), geometry, material };
    };

    scene.add(new THREE.PointLight(0xffffff, 1, 100), new THREE.AmbientLight(0x404040));

    const loadData = async () => {
        setLoading(true);
        try {
            const data = await fetchML2Regime(universe, ticker);
            if (!isMounted) return;
            setRegimeData(data);
            const { mesh, geometry, material } = createSpectralMesh(data.spectral_summary || data.spectral_energy || {});
            scene.add(mesh);
            currentMesh = mesh;
            currentGeom = geometry;
            currentMat = material;
            sceneRef.current = { scene, mesh, data };
            scene.background = new THREE.Color({ Bear: 0x1a0505, Neutral: 0x05051a, Bull: 0x051a05 }[data.regime] || 0x0a0a0f);
            setLoading(false);
        } catch (err) {
            if (isMounted) setLoading(false);
        }
    };
    loadData();

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      if (currentMesh) currentMesh.rotation.z += 0.001;
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    const handleResize = () => {
      const w = mountNode.clientWidth, h = mountNode.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      isMounted = false;
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationFrameId);
      if (mountNode && renderer.domElement) mountNode.removeChild(renderer.domElement);
      renderer.dispose();
      controls.dispose();
      if (currentGeom) currentGeom.dispose();
      if (currentMat) currentMat.dispose();
    };
  }, [universe, ticker]);

  return (
    <div className="relative border border-terminal-green/20 rounded-xl overflow-hidden bg-black/40">
      <div ref={mountRef} className="w-full h-[600px]" />
      
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/60 backdrop-blur-sm">
            <div className="flex flex-col items-center gap-4">
                <div className="w-12 h-12 border-4 border-terminal-green border-t-transparent rounded-full animate-spin"></div>
                <div className="text-terminal-green font-mono animate-pulse">SOLVING_TRANSITION_MATRICES...</div>
            </div>
        </div>
      )}

      {regimeData && (
        <div className="absolute top-6 left-6 p-6 bg-black/80 backdrop-blur-md border border-terminal-green/30 rounded-lg shadow-2xl">
          <div className="text-[10px] text-terminal-blue font-bold tracking-widest uppercase mb-1">Current State</div>
          <h3 className="text-3xl font-black text-terminal-green uppercase mb-4 tracking-tight">
            Regime: {regimeData?.regime || "UNDEFINED"}
          </h3>
          
          <div className="grid grid-cols-2 gap-8">
              <div>
                  <div className="text-[10px] text-terminal-blue font-bold tracking-widest uppercase mb-1">Stability</div>
                  <div className="text-4xl font-mono font-black text-terminal-white">
                    {(regimeData?.stability || 0).toFixed(1)}%
                  </div>
              </div>
              <div>
                  <div className="text-[10px] text-terminal-blue font-bold tracking-widest uppercase mb-1">State Type</div>
                  <div className="text-xl font-mono text-terminal-yellow">
                    {regimeData.regime_type || "HMM_GAUSSIAN"}
                  </div>
              </div>
          </div>

          <div className="mt-6 pt-6 border-t border-terminal-green/10">
              <div className="text-[10px] text-terminal-blue font-bold tracking-widest uppercase mb-2">Spectral Density</div>
              <div className="flex gap-2 items-end h-8">
                {Object.entries(regimeData.spectral_summary || {}).map(([key, value]) => (
                    <div key={key} className="flex-1 group relative">
                        <div 
                            className="bg-terminal-green/40 hover:bg-terminal-green transition-all" 
                            style={{ height: `${Math.min(value / 100, 100)}%` }}
                        ></div>
                        <div className="absolute -top-6 left-0 text-[8px] opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                            {key}: {(value || 0).toFixed(0)}
                        </div>
                    </div>
                ))}
              </div>
          </div>
        </div>
      )}
    </div>
  );
}
