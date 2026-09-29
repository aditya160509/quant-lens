import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls";

export default function RegimeWaves3D({ ticker }) {
  const mountRef = useRef(null);
  const [data, setData] = useState(null);
  const sceneRef = useRef(null);

  useEffect(() => {
    if (!ticker) return;

    // Scene setup
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0a0f);

    const width = mountRef.current.clientWidth || 800;
    const height = 600;

    const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
    camera.position.set(0, 30, 50);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(window.devicePixelRatio);
    mountRef.current.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    // Spectral Mountain Mesh
    const createSpectralMesh = (energyData) => {
      const geometry = new THREE.PlaneGeometry(100, 100, 64, 64);
      const vertices = geometry.attributes.position.array;

      // Modulate height by spectral energy
      for (let i = 0; i < vertices.length; i += 3) {
        const x = vertices[i];
        const y = vertices[i + 1];
        const dist = Math.sqrt(x * x + y * y);
        const freq = dist / 10;

        // Mix trend/swing/noise energy
        const h =
          energyData.trend * Math.sin(freq * 0.5) * 0.5 +
          energyData.swing * Math.sin(freq * 2.0) * 0.3 +
          energyData.noise * Math.sin(freq * 5.0) * 0.2;

        vertices[i + 2] = h * 15; // Amplify height
      }

      geometry.attributes.position.needsUpdate = true;
      geometry.computeVertexNormals();

      const material = new THREE.MeshPhongMaterial({
        color: 0x00ff88,
        wireframe: true,
        transparent: true,
        opacity: 0.8,
        emissive: 0x00ff88,
        emissiveIntensity: 0.2,
        side: THREE.DoubleSide
      });

      return new THREE.Mesh(geometry, material);
    };

    // Lighting
    const light = new THREE.PointLight(0xffffff, 1, 100);
    light.position.set(0, 50, 50);
    scene.add(light);
    scene.add(new THREE.AmbientLight(0x404040));

    // Fetch regime data
    fetch(`/api/ml/v2/regime/${ticker}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.error) throw new Error(data.error);
        setData(data);
        const mesh = createSpectralMesh(data.spectral_energy);
        mesh.rotation.x = -Math.PI / 2;
        scene.add(mesh);
        sceneRef.current = { scene, mesh };

        // Dynamic background
        const colors = {
          0: 0x3d0000, // Bear
          1: 0x111111, // Neutral
          2: 0x003d00, // Bull
        };
        scene.background = new THREE.Color(colors[data.regime_id] || 0x0a0a0f);
      })
      .catch(err => {
        console.error("Regime fetch error:", err);
      });

    // Animation loop
    let frameId;
    const animate = () => {
      frameId = requestAnimationFrame(animate);
      controls.update();
      if (sceneRef.current?.mesh) {
        sceneRef.current.mesh.rotation.z += 0.001;
      }
      renderer.render(scene, camera);
    };
    animate();

    const handleResize = () => {
      const w = mountRef.current.clientWidth;
      camera.aspect = w / height;
      camera.updateProjectionMatrix();
      renderer.setSize(w, height);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(frameId);
      window.removeEventListener('resize', handleResize);
      if (mountRef.current && renderer.domElement) {
        mountRef.current.removeChild(renderer.domElement);
      }
      renderer.dispose();
    };
  }, [ticker]);

  return (
    <div className="relative w-full overflow-hidden bg-black/50 rounded-xl border border-terminal-cyan/20">
      <div ref={mountRef} className="w-full h-[600px]" />
      
      {data && (
        <div className="absolute bottom-6 left-6 p-4 bg-black/80 border border-terminal-cyan/30 rounded-lg backdrop-blur-md">
          <div className="text-terminal-cyan text-sm font-mono mb-1">CURRENT REGIME</div>
          <div className="text-3xl font-bold tracking-tighter text-white uppercase">{data.regime_name}</div>
          <div className="mt-2 flex items-center gap-2">
            <div className="w-32 h-2 bg-gray-800 rounded-full overflow-hidden">
              <div 
                className="h-full bg-terminal-cyan transition-all duration-1000" 
                style={{ width: `${data.stability_index}%` }} 
              />
            </div>
            <span className="text-terminal-cyan font-mono text-xs">{data.stability_index}% STABILITY</span>
          </div>
        </div>
      )}
      
      <div className="absolute top-6 left-6 pointer-events-none">
        <h2 className="text-terminal-cyan font-mono text-xl font-bold tracking-widest uppercase">
          Quantum Regime Waves
        </h2>
        <p className="text-terminal-cyan/60 text-xs font-mono">3D SPECTRAL DECOMPOSITION MAPPED TO HIDDEN MARKOV NODES</p>
      </div>
    </div>
  );
}
