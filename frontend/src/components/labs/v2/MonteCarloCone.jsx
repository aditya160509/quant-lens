import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { fetchML2MonteCarlo } from "@/lib/api";

export default function MonteCarloCone({ universe, ticker }) {
  const mountRef = useRef(null);
  const [mcData, setMcData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let animationFrameId;
    let isMounted = true;
    const mountNode = mountRef.current;
    if (!mountNode) return;

    const width = mountNode.clientWidth || 800;
    const height = mountNode.clientHeight || 600;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0014);

    const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
    camera.position.set(40, 20, 60);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    mountNode.appendChild(renderer.domElement);

    const loadData = async () => {
        setLoading(true);
        try {
            const data = await fetchML2MonteCarlo(universe, ticker);
            if (!isMounted) return;
            setMcData(data);
            
            const S0 = data.current_price;
            const horizon = data.horizon || 30;
            const paths = data.simulated_paths || [];
            
            paths.forEach((path) => {
                const points = path.map((price, day) => new THREE.Vector3(
                    (day / horizon) * 60 - 30,
                    (price / S0 - 1) * 30, 
                    (Math.random() - 0.5) * 10
                ));
                const line = new THREE.Line(
                    new THREE.BufferGeometry().setFromPoints(points),
                    new THREE.LineBasicMaterial({ color: 0x00ffaa, transparent: true, opacity: 0.1 })
                );
                scene.add(line);
            });

            const percentiles = data.percentiles || {};
            const p5_norm = (percentiles.p5 / S0 - 1) * 30;
            const p95_norm = (percentiles.p95 / S0 - 1) * 30;
            const cloud = new THREE.Mesh(
                new THREE.CylinderGeometry(Math.abs(p95_norm - p5_norm) / 2, 0.1, 60, 32, 1, true),
                new THREE.MeshBasicMaterial({ color: 0x0088ff, transparent: true, opacity: 0.05, side: THREE.DoubleSide, wireframe: true })
            );
            cloud.rotation.z = Math.PI / 2;
            cloud.position.set(0, (p95_norm + p5_norm) / 2, 0);
            scene.add(cloud);

            const gridHelper = new THREE.GridHelper(100, 20, 0x444444, 0x222222);
            gridHelper.position.y = -20;
            scene.add(gridHelper);
            scene.add(new THREE.AmbientLight(0x404040));
            
            const light = new THREE.PointLight(0xffffff, 1);
            light.position.set(50, 50, 50);
            scene.add(light);
            
            setLoading(false);
        } catch (err) {
            if (isMounted) setLoading(false);
        }
    };
    loadData();

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      const time = Date.now() * 0.0005;
      camera.position.x = 60 * Math.cos(time);
      camera.position.z = 60 * Math.sin(time);
      camera.lookAt(0, 0, 0);
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      isMounted = false;
      cancelAnimationFrame(animationFrameId);
      if (mountNode && renderer.domElement) mountNode.removeChild(renderer.domElement);
      renderer.dispose();
    };
  }, [universe, ticker]);

  return (
    <div className="relative border border-terminal-green/20 rounded-xl overflow-hidden bg-black/40">
      <div ref={mountRef} className="w-full h-[600px]" />
      
      {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/60 backdrop-blur-sm">
              <div className="flex flex-col items-center gap-4">
                  <div className="w-12 h-12 border-4 border-terminal-yellow border-t-transparent rounded-full animate-spin"></div>
                  <div className="text-terminal-yellow font-mono animate-pulse">WARPING_TIME_AXIS...</div>
              </div>
          </div>
      )}

      {mcData && (
        <div className="absolute bottom-6 right-6 w-96 p-6 bg-black/80 backdrop-blur-md border border-terminal-green/30 rounded-lg shadow-2xl">
          <div className="text-[10px] text-terminal-blue font-bold tracking-widest uppercase mb-1">Statistical Projection</div>
          <h3 className="text-2xl font-black text-terminal-white uppercase mb-4 tracking-tight">
            Monte Carlo {mcData?.horizon || 30}D
          </h3>
          
          <div className="space-y-4">
              <div className="flex justify-between items-end border-b border-white/5 pb-2">
                  <span className="text-[10px] uppercase font-bold text-gray-400">Profit Probability</span>
                  <span className={`text-2xl font-black font-mono ${(mcData?.prob_profit || 0) > 50 ? 'text-terminal-green' : 'text-terminal-red'}`}>
                    {(mcData?.prob_profit || 0).toFixed(1)}%
                  </span>
              </div>

              <div className="grid grid-cols-2 gap-4">
                  <div className="bg-white/5 p-3 rounded">
                      <div className="text-[9px] text-terminal-blue font-bold uppercase mb-1">Bull Target (P95)</div>
                      <div className="text-base font-mono font-bold text-terminal-green">${(mcData?.percentiles?.p95 || 0).toFixed(2)}</div>
                  </div>
                  <div className="bg-white/5 p-3 rounded">
                      <div className="text-[9px] text-terminal-blue font-bold uppercase mb-1">Median (P50)</div>
                      <div className="text-base font-mono font-bold text-terminal-white">${(mcData?.percentiles?.p50 || 0).toFixed(2)}</div>
                  </div>
              </div>
              
              <div className="bg-terminal-green/5 border border-terminal-green/10 p-3 rounded">
                  <div className="text-[9px] text-terminal-green font-bold uppercase mb-1">GARCH(1,1) Volatility Model</div>
                  <div className="text-[10px] text-terminal-green/70 font-mono leading-tight">
                      Simulation anchored at ${(mcData?.current_price || 0).toFixed(2)}. 
                      System generated 50,000 recursive paths for this horizon.
                  </div>
              </div>
          </div>
        </div>
      )}

      <div className="absolute top-6 left-6 pointer-events-none">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-terminal-green animate-pulse"></div>
            <div className="text-[8px] font-mono text-terminal-green uppercase tracking-[0.3em]">
                Live Probability Stream
            </div>
          </div>
      </div>
    </div>
  );
}
