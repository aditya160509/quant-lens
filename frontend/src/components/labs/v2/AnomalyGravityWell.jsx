import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { fetchML2Anomalies } from "@/lib/api";

export default function AnomalyGravityWell({ universe, ticker }) {
  const mountRef = useRef(null);
  const [anomalyData, setAnomalyData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let animationFrameId;
    const mountNode = mountRef.current;
    if (!mountNode) return;

    let isMounted = true;
    const width = mountNode.clientWidth || 800;
    const height = mountNode.clientHeight || 600;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x020205);

    const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
    camera.position.set(0, 40, 40);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    mountNode.appendChild(renderer.domElement);

    const gridSize = 60;
    const geometry = new THREE.PlaneGeometry(gridSize, gridSize, 40, 40);
    const vertices = geometry.attributes.position.array;

    const loadData = async () => {
        setLoading(true);
        try {
            const data = await fetchML2Anomalies(universe, ticker);
            if (!isMounted) return;
            setAnomalyData(data);
            
            const suspicion = data.suspicion_score || 0;
            const isAnomaly = data.is_anomaly;

            for (let i = 0; i < vertices.length; i += 3) {
                const x = vertices[i];
                const y = vertices[i + 1];
                const dist = Math.sqrt(x * x + y * y);
                const depth = (-suspicion / 5) * Math.exp(-dist / 8);
                const noise = Math.sin(x * 0.5) * Math.cos(y * 0.5) * 0.5;
                vertices[i + 2] = depth + noise;
            }

            geometry.attributes.position.needsUpdate = true;
            geometry.computeVertexNormals();

            const material = new THREE.MeshPhongMaterial({
                color: isAnomaly ? 0xff3333 : 0x00d4ff,
                wireframe: true,
                transparent: true,
                opacity: 0.6,
                side: THREE.DoubleSide,
            });

            const mesh = new THREE.Mesh(geometry, material);
            mesh.rotation.x = -Math.PI / 2;
            scene.add(mesh);

            if (data.historical_anomalies) {
                data.historical_anomalies.slice(-15).forEach((evt, idx) => {
                    const suspicionLevel = evt.suspicion || 50;
                    const sphere = new THREE.Mesh(
                        new THREE.SphereGeometry(suspicionLevel / 60, 16, 16),
                        new THREE.MeshPhongMaterial({
                            color: 0xff4444,
                            emissive: 0xff0000,
                            emissiveIntensity: 0.5,
                            transparent: true,
                            opacity: 0.7,
                        }),
                    );
                    
                    const angle = (idx / 15) * Math.PI * 2;
                    const radius = 10 + (idx * 1.5);
                    sphere.position.set(
                        Math.cos(angle) * radius,
                        suspicionLevel / 10,
                        Math.sin(angle) * radius
                    );
                    scene.add(sphere);
                });
            }

            const ambientLight = new THREE.AmbientLight(0x202020);
            scene.add(ambientLight);
            const spotlight = new THREE.SpotLight(0xffffff, 1);
            spotlight.position.set(0, 50, 0);
            scene.add(spotlight);
            
            setLoading(false);
        } catch (err) {
            if (isMounted) {
                console.error("Failed to fetch anomaly data:", err);
                setLoading(false);
            }
        }
    };
    loadData();

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      scene.rotation.y += 0.002;
      renderer.render(scene, camera);
    };
    animate();

    const handleResize = () => {
      if (!mountNode) return;
      const w = mountNode.clientWidth;
      const h = mountNode.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      isMounted = false;
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationFrameId);
      if (mountNode && renderer.domElement) {
        mountNode.removeChild(renderer.domElement);
      }
      renderer.dispose();
      geometry.dispose();
    };
  }, [universe, ticker]);

  return (
    <div className="relative border border-terminal-green/20 rounded-xl overflow-hidden bg-black/40">
      <div ref={mountRef} className="w-full h-[600px]" />
      
      {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/60 backdrop-blur-sm">
              <div className="flex flex-col items-center gap-4">
                  <div className="w-12 h-12 border-4 border-terminal-red border-t-transparent rounded-full animate-spin"></div>
                  <div className="text-terminal-red font-mono animate-pulse">ISOLATING_DEVIATIONS...</div>
              </div>
          </div>
      )}

      {anomalyData && (
        <div className="absolute top-6 right-6 w-80 p-6 bg-black/80 backdrop-blur-md border border-terminal-red/30 rounded-lg shadow-2xl">
          <div className="flex items-center gap-2 mb-2">
            <div className={`w-2 h-2 rounded-full ${anomalyData.is_anomaly ? 'bg-red-500 animate-ping' : 'bg-blue-500'}`}></div>
            <div className="text-[10px] text-terminal-blue font-bold tracking-widest uppercase">Gravity Potential</div>
          </div>
          
          <h3 className={`text-2xl font-black mb-4 tracking-tight ${anomalyData.is_anomaly ? 'text-terminal-red' : 'text-terminal-blue'}`}>
            {anomalyData.is_anomaly ? 'ANOMALY_DETECTED' : 'SIGNAL_STABLE'}
          </h3>
          
          <div className="space-y-4">
              <div>
                  <div className="flex justify-between text-[10px] uppercase font-bold text-gray-400 mb-1">
                      <span>Suspicion Index</span>
                      <span>{(anomalyData?.suspicion_score || 0).toFixed(1)}</span>
                  </div>
                  <div className="h-1.5 w-full bg-gray-800 rounded-full overflow-hidden">
                      <div 
                        className={`h-full transition-all duration-1000 ${anomalyData?.is_anomaly ? 'bg-terminal-red' : 'bg-terminal-blue'}`}
                        style={{ width: `${anomalyData?.suspicion_score || 0}%` }}
                      ></div>
                  </div>
              </div>

              <div className="pt-4 border-t border-white/5">
                  <div className="text-[10px] text-terminal-blue font-bold tracking-widest uppercase mb-2">Historical Fractures</div>
                  <div className="max-h-40 overflow-y-auto pr-2 custom-scrollbar">
                      {anomalyData.historical_anomalies?.slice(-10).reverse().map((e, i) => (
                        <div key={i} className="flex justify-between items-center py-2 border-b border-white/5 last:border-0 hover:bg-white/5 transition-colors px-1 rounded">
                            <span className="text-[10px] font-mono text-gray-500">{e.timestamp?.split('T')[0] || e.date}</span>
                            <span className="text-[10px] font-mono font-bold text-terminal-red">{e.suspicion?.toFixed(1)}</span>
                        </div>
                      ))}
                  </div>
              </div>
          </div>
        </div>
      )}

      <div className="absolute bottom-6 left-6 pointer-events-none">
          <div className="text-[8px] font-mono text-terminal-blue/40 uppercase tracking-[0.3em]">
              Isolation Forest v2.4 // Decoupled Manifold Analysis
          </div>
      </div>
    </div>
  );
}
