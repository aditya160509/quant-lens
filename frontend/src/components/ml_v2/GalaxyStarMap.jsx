import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls";

export default function GalaxyStarMap() {
  const mountRef = useRef(null);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const sceneRef = useRef({ meshes: [] });

  useEffect(() => {
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x000008);

    const width = mountRef.current.clientWidth || 800;
    const height = 600;

    const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 2000);
    camera.position.set(0, 0, 300);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(window.devicePixelRatio);
    mountRef.current.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.5;

    // Star background
    const starGeo = new THREE.BufferGeometry();
    const starPos = [];
    for(let i=0; i<8000; i++){
        starPos.push((Math.random()-0.5)*1500, (Math.random()-0.5)*1500, (Math.random()-0.5)*1500);
    }
    starGeo.setAttribute('position', new THREE.Float32BufferAttribute(starPos, 3));
    const starMat = new THREE.PointsMaterial({ color: 0xffffff, size: 0.8 });
    scene.add(new THREE.Points(starGeo, starMat));

    // Fetch Universe
    fetch('/api/ml/v2/galaxy/universe')
      .then(res => res.json())
      .then(universe => {
        setLoading(false);
        if(!universe || universe.length === 0) {
            // Mock if empty for demo
            universe = generateMockUniverse();
        }

        universe.forEach(stock => {
            const size = Math.log10(stock.market_cap / 1e6) * 0.8;
            const geo = new THREE.SphereGeometry(size || 1, 16, 16);
            
            const sectorColors = {
                'Technology': 0x00ffff,
                'Healthcare': 0xff00ff,
                'Finance': 0xffff00,
                'Energy': 0xff8800,
                'Consumer': 0x00ff00,
                'Industrial': 0x8888ff
            };
            const color = sectorColors[stock.sector] || 0xffffff;
            
            const mat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.8 });
            const mesh = new THREE.Mesh(geo, mat);
            mesh.position.set(stock.x * 20, stock.y * 20, stock.z * 20);
            mesh.userData = stock;
            
            scene.add(mesh);
            sceneRef.current.meshes.push(mesh);
        });
      });

    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();

    const onClick = (e) => {
        const rect = renderer.domElement.getBoundingClientRect();
        mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
        mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

        raycaster.setFromCamera(mouse, camera);
        const intersects = raycaster.intersectObjects(sceneRef.current.meshes);
        
        if(intersects.length > 0) {
            const stock = intersects[0].object.userData;
            setSelected(stock);
            controls.autoRotate = false;
            
            // Zoom to target
            const target = intersects[0].object.position;
            new TWEEN.Tween(camera.position).to({
                x: target.x + 30,
                y: target.y + 30,
                z: target.z + 30
            }, 1000).easing(TWEEN.Easing.Quadratic.Out).start();
            controls.target.copy(target);
        }
    };
    mountRef.current.addEventListener('click', onClick);

    let frameId;
    const animate = () => {
      frameId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(frameId);
      if (mountRef.current) {
          mountRef.current.removeEventListener('click', onClick);
          if(renderer.domElement) mountRef.current.removeChild(renderer.domElement);
      }
      renderer.dispose();
    };
  }, []);

  return (
    <div className="relative w-full bg-black/90 rounded-2xl border border-cyan-500/10 overflow-hidden cursor-crosshair">
      <div ref={mountRef} className="w-full h-[700px]" />
      
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/80 backdrop-blur-sm z-50">
            <div className="text-terminal-cyan font-mono animate-pulse">WARPING TO CROSS-SECTOR MANIFOLD...</div>
        </div>
      )}

      {selected && (
        <div className="absolute top-10 right-10 p-6 bg-black/80 border border-cyan-500/30 rounded-2xl backdrop-blur-xl w-72 animate-in fade-in slide-in-from-right">
            <h3 className="text-cyan-400 font-bold text-xl mb-1">{selected.ticker}</h3>
            <p className="text-white/60 text-xs font-mono mb-4">{selected.name}</p>
            
            <div className="space-y-4">
                <div>
                    <span className="text-white/40 text-[10px] uppercase block mb-1">Sector Manifold</span>
                    <span className="text-cyan-300 font-mono text-sm uppercase">{selected.sector}</span>
                </div>
                <div>
                    <span className="text-white/40 text-[10px] uppercase block mb-1">Market Cap</span>
                    <span className="text-white font-mono text-sm">${(selected.market_cap / 1e9).toFixed(1)}B</span>
                </div>
                <div className="pt-4 border-t border-white/10">
                    <button 
                        className="w-full py-2 bg-cyan-500/20 text-cyan-400 text-[10px] font-bold uppercase tracking-widest border border-cyan-500/30 hover:bg-cyan-500/40 transition-colors"
                        onClick={() => setSelected(null)}
                    >
                        Reset Manifest
                    </button>
                </div>
            </div>
        </div>
      )}

      <div className="absolute bottom-10 left-10 pointer-events-none">
        <h2 className="text-terminal-cyan font-mono text-2xl font-bold tracking-tighter uppercase mb-1">The Galaxy Manifold</h2>
        <p className="text-white/40 text-[10px] font-mono">150+ DIMENSIONAL FUNDAMENTAL VECTORS REDUCED BY UMAP</p>
      </div>
    </div>
  );
}

function generateMockUniverse() {
    const sectors = ['Technology', 'Healthcare', 'Finance', 'Energy', 'Consumer', 'Industrial'];
    const tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'BRK.B', 'UNH', 'JNJ', 'JPM', 'XOM', 'V', 'PG', 'MA', 'HD', 'CVX', 'ABBV', 'KO', 'PEP'];
    return tickers.map((t, i) => ({
        ticker: t,
        name: `Institutional Equity ${t}`,
        sector: sectors[i % sectors.length],
        x: (Math.random() - 0.5) * 20,
        y: (Math.random() - 0.5) * 20,
        z: (Math.random() - 0.5) * 20,
        market_cap: Math.random() * 2e12 + 1e11
    }));
}
