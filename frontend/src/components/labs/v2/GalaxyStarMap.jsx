import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls";
import { fetchML2GalaxyUniverse, fetchML2GalaxySimilar } from "@/lib/api";

export default function GalaxyStarMap({ universe }) {
  const mountRef = useRef(null);
  const [selectedStock, setSelectedStock] = useState(null);
  const [similarStocks, setSimilarStocks] = useState([]);
  const [loading, setLoading] = useState(true);
  const sceneRef = useRef({ universe: [], stockMeshes: [] });

  const animateCameraTo = (camera, target, controls) => {
    const startPos = camera.position.clone();
    const distance = 40;
    const endPos = target.clone().add(new THREE.Vector3(distance, distance, distance));

    let progress = 0;
    const step = () => {
      progress += 0.03;
      if (progress > 1) {
        controls.target.copy(target);
        return;
      }
      camera.position.lerpVectors(startPos, endPos, progress);
      camera.lookAt(target);
      requestAnimationFrame(step);
    };
    step();
  };

  useEffect(() => {
    const mountNode = mountRef.current;
    if (!mountNode) return;

    let isMounted = true;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x000008);

    const width = mountNode.clientWidth || 1200;
    const height = mountNode.clientHeight || 800;
    const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 2000);
    camera.position.set(0, 50, 200);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    mountNode.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;

    // Star field
    const starGeometry = new THREE.BufferGeometry();
    const starVertices = [];
    for (let i = 0; i < 15000; i++) {
      starVertices.push((Math.random() - 0.5) * 1000, (Math.random() - 0.5) * 1000, (Math.random() - 0.5) * 1000);
    }
    starGeometry.setAttribute("position", new THREE.Float32BufferAttribute(starVertices, 3));
    const stars = new THREE.Points(starGeometry, new THREE.PointsMaterial({ color: 0xffffff, size: 0.7, transparent: true, opacity: 0.8 }));
    scene.add(stars);

    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();
    const sectorColors = { Technology: 0x00ffff, Healthcare: 0xff00ff, Financial: 0xffff00, Energy: 0xff8800, Consumer: 0x00ff00, Industrial: 0x8888ff };

    const loadData = async () => {
        setLoading(true);
        try {
            const data = await fetchML2GalaxyUniverse(universe);
            if (!isMounted) return;
            sceneRef.current.universe = data;
            data.forEach((stock) => {
                const size = Math.max(0.5, Math.log10((stock.market_cap || 1e9) / 1e8));
                const mat = new THREE.MeshPhongMaterial({ color: sectorColors[stock.sector] || 0xffffff, emissive: sectorColors[stock.sector] || 0xffffff, emissiveIntensity: 0.3 });
                const mesh = new THREE.Mesh(new THREE.SphereGeometry(size, 16, 16), mat);
                mesh.position.set(stock.x * 15, stock.y * 15, stock.z * 15);
                mesh.userData = stock;
                scene.add(mesh);
                sceneRef.current.stockMeshes.push(mesh);
            });
            setLoading(false);
        } catch (err) {
            if (isMounted) setLoading(false);
        }
    };
    loadData();

    const onClick = (event) => {
      const rect = renderer.domElement.getBoundingClientRect();
      mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObjects(sceneRef.current.stockMeshes || []);
      if (intersects.length > 0) {
        const stock = intersects[0].object.userData;
        setSelectedStock(stock);
        fetchML2GalaxySimilar(universe, stock.ticker).then(setSimilarStocks).catch(console.error);
        animateCameraTo(camera, intersects[0].object.position.clone(), controls);
      }
    };
    renderer.domElement.addEventListener("click", onClick);

    let animationFrameId;
    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      isMounted = false;
      renderer.domElement.removeEventListener("click", onClick);
      cancelAnimationFrame(animationFrameId);
      if (mountNode && renderer.domElement) mountNode.removeChild(renderer.domElement);
      renderer.dispose();
      starGeometry.dispose();
    };
  }, [universe]);

  return (
    <div className="relative w-full h-[800px] border border-terminal-blue/20 rounded-2xl overflow-hidden bg-[#000008]">
      <div ref={mountRef} className="w-full h-full" />
      
      {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/80 backdrop-blur-xl">
              <div className="flex flex-col items-center gap-6">
                  <div className="relative">
                      <div className="w-24 h-24 border-2 border-terminal-blue/20 rounded-full"></div>
                      <div className="absolute top-0 left-0 w-24 h-24 border-t-2 border-terminal-blue rounded-full animate-spin"></div>
                  </div>
                  <div className="flex flex-col items-center">
                      <div className="text-terminal-blue font-mono text-lg tracking-[0.2em] animate-pulse uppercase">Mapping_Market_Galaxy</div>
                      <div className="text-[10px] text-terminal-blue/50 font-mono mt-2 uppercase tracking-widest">Running UMAP Dimensionality Reduction</div>
                  </div>
              </div>
          </div>
      )}

      {selectedStock && (
        <div className="absolute top-8 left-8 w-80 p-8 bg-black/90 backdrop-blur-2xl border border-terminal-blue/40 rounded-xl shadow-[0_0_40px_rgba(0,212,255,0.2)]">
          <div className="text-[10px] text-terminal-blue font-bold tracking-widest uppercase mb-1">Target Identified</div>
          <h3 className="text-3xl font-black text-terminal-white uppercase tracking-tight mb-2">
            {selectedStock.ticker}
          </h3>
          <div className="text-sm font-mono text-terminal-blue mb-6 uppercase tracking-wider">
              {selectedStock.sector} {'//'} {selectedStock.name}
          </div>
          
          <div className="space-y-6">
              <div className="pt-4 border-t border-white/10">
                  <div className="text-[10px] text-gray-500 font-bold uppercase mb-4 tracking-widest">Structural DNA Matches</div>
                  <div className="space-y-3">
                      {similarStocks.map((s) => (
                        <div key={s.ticker} className="flex items-center justify-between p-2 rounded hover:bg-white/5 transition-colors border border-transparent hover:border-terminal-blue/20">
                            <div className="flex flex-col">
                                <span className="text-sm font-bold text-terminal-white">{s.ticker}</span>
                                <span className="text-[9px] text-gray-500 uppercase">{s.sector}</span>
                            </div>
                            <div className="text-right">
                                <span className="text-[10px] font-mono font-bold text-terminal-blue">${(s.market_cap / 1e9).toFixed(1)}B</span>
                            </div>
                        </div>
                      ))}
                      {similarStocks.length === 0 && <div className="text-[10px] text-gray-600 font-mono">SCANNING_FOR_PROXIMITY...</div>}
                  </div>
              </div>
          </div>

          <button 
              onClick={() => setSelectedStock(null)}
              className="mt-8 w-full py-2 border border-terminal-blue/20 hover:border-terminal-blue/60 text-terminal-blue/60 hover:text-terminal-blue text-[10px] font-bold uppercase transition-all"
          >
              Reset Perspective
          </button>
        </div>
      )}

      <div className="absolute bottom-8 left-8 p-4 bg-black/40 backdrop-blur-sm rounded-lg border border-white/5">
        <div className="text-[10px] font-mono text-gray-400 mb-2 font-bold uppercase tracking-widest leading-relaxed">
            UMAP High-Dimensional Projection // 150+ Metrics Per Node
        </div>
        <div className="flex gap-4">
            <div className="flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-[#00ffff]"></div>
                <span className="text-[8px] text-gray-500 font-bold uppercase">Tech</span>
            </div>
            <div className="flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-[#ff00ff]"></div>
                <span className="text-[8px] text-gray-500 font-bold uppercase">Health</span>
            </div>
            <div className="flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-[#ffff00]"></div>
                <span className="text-[8px] text-gray-500 font-bold uppercase">Finance</span>
            </div>
            <div className="flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-[#00ff00]"></div>
                <span className="text-[8px] text-gray-500 font-bold uppercase">Consumer</span>
            </div>
        </div>
      </div>
    </div>
  );
}
