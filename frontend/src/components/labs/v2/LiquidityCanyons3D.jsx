import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls";
import { fetchML2Liquidity } from "@/lib/api";

// Helper function for text sprites
function createTextSprite(text, color) {
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  canvas.width = 256;
  canvas.height = 64;

  ctx.fillStyle = color;
  ctx.font = "Bold 40px Arial";
  ctx.fillText(text, 10, 45);

  const texture = new THREE.CanvasTexture(canvas);
  const material = new THREE.SpriteMaterial({ map: texture });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(20, 5, 1);

  return sprite;
}

export default function LiquidityCanyons3D({ universe, ticker }) {
  const mountRef = useRef(null);
  const [liquidityData, setLiquidityData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let animationFrameId;
    let isMounted = true;
    const mountNode = mountRef.current;
    if (!mountNode) return;

    const width = mountNode.clientWidth || 800;
    const height = mountNode.clientHeight || 600;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x050510);

    const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
    camera.position.set(0, 100, 150);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    mountNode.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    scene.add(new THREE.AmbientLight(0x404040));
    const pointLight = new THREE.PointLight(0xffffff, 1, 300);
    pointLight.position.set(0, 150, 100);
    scene.add(pointLight);

    const loadData = async () => {
        setLoading(true);
        try {
            const data = await fetchML2Liquidity(universe, ticker);
            if (!isMounted) return;
            setLiquidityData(data);
            
            const profile = data.volume_profile || [];
            if (profile.length === 0) {
                setLoading(false);
                return;
            }
            
            const maxVol = Math.max(...profile.map((b) => b.volume || 0));
            const poc = data.poc;
            const vah = data.vah;
            const val = data.val;
            const voids = data.liquidity_voids || [];

            profile.forEach((bucket, idx) => {
              const h = ((bucket.volume || 0) / (maxVol || 1)) * 100;
              const geometry = new THREE.BoxGeometry(2, h, 2);
              const isVoid = voids.some((v) => Math.abs(v.price - bucket.price) < 0.1);
              let color = 0x0088ff;
              if (isVoid) color = 0xff3333;
              else if (Math.abs(bucket.price - poc) < 0.1) color = 0xffff00;
              else if (bucket.price >= val && bucket.price <= vah) color = 0x00ff88;

              const material = new THREE.MeshPhongMaterial({
                color,
                emissive: color,
                emissiveIntensity: 0.1,
                transparent: true,
                opacity: isVoid ? 0.3 : 0.8,
              });
              const pillar = new THREE.Mesh(geometry, material);
              pillar.position.set((idx - profile.length / 2) * 3, h / 2, 0);
              scene.add(pillar);
            });

            const addMarker = (price, label, color) => {
              const idx = profile.findIndex((b) => Math.abs(b.price - price) < 1);
              if (idx === -1) return;
              const sprite = createTextSprite(label, color);
              sprite.position.set((idx - profile.length / 2) * 3, 120, 0);
              scene.add(sprite);
            };
            addMarker(vah, "VAH", "#00ff88");
            addMarker(val, "VAL", "#00ff88");
            addMarker(poc, "POC", "#ffff00");

            setLoading(false);
        } catch (err) {
            if (isMounted) {
                console.error("Failed to fetch liquidity data:", err);
                setLoading(false);
            }
        }
    };
    loadData();

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      isMounted = false;
      cancelAnimationFrame(animationFrameId);
      if (mountNode && renderer.domElement) mountNode.removeChild(renderer.domElement);
      controls.dispose();
      renderer.dispose();
    };
  }, [universe, ticker]);

  return (
    <div className="relative border border-terminal-green/20 rounded-xl overflow-hidden bg-black/40">
      <div ref={mountRef} className="w-full h-[600px]" />
      
      {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/60 backdrop-blur-sm">
              <div className="flex flex-col items-center gap-4">
                  <div className="w-12 h-12 border-4 border-terminal-blue border-t-transparent rounded-full animate-spin"></div>
                  <div className="text-terminal-blue font-mono animate-pulse">PROFILING_VOLUME_DENSITY...</div>
              </div>
          </div>
      )}

      {liquidityData?.resistance_path && (
        <div className="absolute top-6 left-6 max-w-md p-6 bg-black/80 backdrop-blur-md border border-terminal-green/30 rounded-lg shadow-2xl">
          <div className="text-[10px] text-terminal-blue font-bold tracking-widest uppercase mb-1">Path of Least Resistance</div>
          <h3 className="text-xl font-black text-terminal-white uppercase mb-4 tracking-tight">Institutional Volume Profile</h3>
          
          <p className="text-xs text-terminal-green/90 leading-relaxed font-mono mb-4 italic">
            &quot;{liquidityData.resistance_path.summary}&quot;
          </p>
          
          <div className="grid grid-cols-3 gap-2">
              <div className="bg-white/5 p-2 rounded text-center">
                  <div className="text-[8px] text-gray-500 uppercase font-bold mb-1">Support (VAL)</div>
                  <div className="text-xs font-mono font-bold text-terminal-green">${(liquidityData?.val || 0).toFixed(2)}</div>
              </div>
              <div className="bg-white/5 p-2 rounded text-center">
                  <div className="text-[8px] text-gray-500 uppercase font-bold mb-1">Magnet (POC)</div>
                  <div className="text-xs font-mono font-bold text-terminal-yellow">${(liquidityData?.poc || 0).toFixed(2)}</div>
              </div>
              <div className="bg-white/5 p-2 rounded text-center">
                  <div className="text-[8px] text-gray-500 uppercase font-bold mb-1">Barricade (VAH)</div>
                  <div className="text-xs font-mono font-bold text-terminal-red">${(liquidityData?.vah || 0).toFixed(2)}</div>
              </div>
          </div>
        </div>
      )}

      <div className="absolute bottom-6 right-6">
          <div className="flex flex-col gap-1 items-end">
              <div className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-terminal-green"></div>
                  <span className="text-[8px] font-mono text-gray-400">VALUE_AREA (70%)</span>
              </div>
              <div className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-terminal-yellow"></div>
                  <span className="text-[8px] font-mono text-gray-400">POINT_OF_CONTROL</span>
              </div>
              <div className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-terminal-red"></div>
                  <span className="text-[8px] font-mono text-gray-400">LIQUIDITY_VOID</span>
              </div>
          </div>
      </div>
    </div>
  );
}
