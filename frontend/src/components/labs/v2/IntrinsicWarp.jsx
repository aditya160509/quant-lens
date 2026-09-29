import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls";
import { fetchML2Valuation } from "@/lib/api";

export default function IntrinsicWarp({ universe, ticker }) {
  const mountRef = useRef(null);
  const [valuationData, setValuationData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let animationFrameId;
    let isMounted = true;
    const mountNode = mountRef.current;
    if (!mountNode) return;

    const loadData = async () => {
        setLoading(true);
        try {
            const data = await fetchML2Valuation(universe, ticker);
            if (!isMounted) return;
            setValuationData(data);
            
            const surface = data.surface_grid;
            if (!surface || !surface.values) {
                setLoading(false);
                return;
            }

            const size = surface.values.length;
            const geometry = new THREE.PlaneGeometry(100, 100, size - 1, size - 1);
            const vertices = geometry.attributes.position.array;
            const values = surface.values.flat();
            const maxValue = Math.max(...values);
            const minValue = Math.min(...values);

            for (let i = 0; i < size; i++) {
                for (let j = 0; j < size; j++) {
                    const idx = (i * size + j) * 3;
                    const val = surface.values[i][j];
                    const normalizedHeight = ((val - minValue) / (Math.max(1, maxValue - minValue))) * 40;
                    vertices[idx + 2] = normalizedHeight;
                }
            }
            geometry.attributes.position.needsUpdate = true;
            geometry.computeVertexNormals();

            const material = new THREE.MeshPhongMaterial({
                color: 0x00ff88,
                wireframe: true,
                side: THREE.DoubleSide,
                transparent: true,
                opacity: 0.5,
                emissive: 0x00ff88,
                emissiveIntensity: 0.1
            });
            const mesh = new THREE.Mesh(geometry, material);
            mesh.rotation.x = -Math.PI / 2;
            scene.add(mesh);

            const currentPriceHeight = ((data.current_price - minValue) / (Math.max(1, maxValue - minValue))) * 40;
            const marker = new THREE.Mesh(
                new THREE.TorusGeometry(2, 0.2, 16, 100),
                new THREE.MeshBasicMaterial({ color: 0xff3333 })
            );
            marker.rotation.x = -Math.PI / 2;
            marker.position.set(0, currentPriceHeight, 0);
            scene.add(marker);

            setLoading(false);
        } catch (err) {
            if (isMounted) {
                console.error("Valuation fetch failed:", err);
                setLoading(false);
            }
        }
    };

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x020205);

    const width = mountNode.clientWidth || 1000;
    const height = mountNode.clientHeight || 600;
    const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
    camera.position.set(60, 60, 60);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    mountNode.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    scene.add(new THREE.AmbientLight(0x404040));
    const p1 = new THREE.PointLight(0x00ff88, 1, 200);
    p1.position.set(50, 80, 50);
    scene.add(p1);
    const p2 = new THREE.PointLight(0xff3333, 0.5, 200);
    p2.position.set(-50, -80, -50);
    scene.add(p2);

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
      if (mountNode && renderer.domElement) {
        mountNode.removeChild(renderer.domElement);
      }
      controls.dispose();
      renderer.dispose();
    };
  }, [universe, ticker]);

  return (
    <div className="relative flex flex-col gap-6">
      <div className="relative border border-terminal-green/20 rounded-2xl overflow-hidden bg-black/60 shadow-inner">
        <div ref={mountRef} className="w-full h-[600px]" />
        
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/80 backdrop-blur-xl">
              <div className="flex flex-col items-center gap-6">
                  <div className="w-16 h-16 border-4 border-terminal-green/30 border-t-terminal-green rounded-full animate-spin"></div>
                  <div className="text-terminal-green font-mono text-sm tracking-[0.3em] uppercase animate-pulse">Computing_Intrinsic_Manifold</div>
              </div>
          </div>
        )}

        <div className="absolute top-8 left-8 p-6 bg-black/60 backdrop-blur-md rounded-xl border border-white/10">
            <div className="text-[10px] text-terminal-blue font-bold uppercase tracking-widest mb-1">Model Variance</div>
            <h3 className="text-xl font-black text-terminal-white uppercase mb-4">Monte Carlo DCF Surface</h3>
            <div className="flex flex-col gap-2">
                <div className="flex items-center gap-2">
                    <div className="w-2 h-2 bg-terminal-green"></div>
                    <span className="text-[10px] text-gray-400 font-mono">X-AXIS: REVENUE_GROWTH (0% - 20%)</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-2 h-2 bg-terminal-blue"></div>
                    <span className="text-[10px] text-gray-400 font-mono">Y-AXIS: WACC_DISCOUNT (5% - 15%)</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-2 h-2 bg-white"></div>
                    <span className="text-[10px] text-gray-400 font-mono">Z-AXIS: INTRINSIC_VALUE_DELTA</span>
                </div>
            </div>
        </div>
      </div>

      {valuationData && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Summary Card */}
          <div className="p-8 bg-black/60 border border-terminal-green/20 rounded-2xl backdrop-blur-md shadow-2xl">
            <div className="flex justify-between items-start mb-8">
                <div>
                    <div className="text-[10px] text-terminal-blue font-bold uppercase tracking-widest mb-1">Target Valuation</div>
                    <h3 className="text-3xl font-black text-terminal-white uppercase tracking-tight">Financial Equilibrium</h3>
                </div>
                <div className={`px-4 py-2 rounded font-mono font-bold text-lg ${(valuationData?.upside || 0) > 0 ? 'bg-terminal-green/20 text-terminal-green' : 'bg-terminal-red/20 text-terminal-red'}`}>
                    {(valuationData?.upside || 0) > 0 ? '+' : ''}{(valuationData?.upside || 0).toFixed(1)}% UPSIDE
                </div>
            </div>

            <div className="grid grid-cols-2 gap-8 mb-8">
                <div className="p-4 bg-white/5 rounded-xl border border-white/5">
                    <div className="text-[10px] text-gray-500 font-bold uppercase mb-1">Current Price</div>
                    <div className="text-2xl font-mono font-black text-terminal-white">${(valuationData?.current_price || 0).toFixed(2)}</div>
                </div>
                <div className="p-4 bg-terminal-green/5 rounded-xl border border-terminal-green/20">
                    <div className="text-[10px] text-terminal-green font-bold uppercase mb-1">Intrinsic (Median)</div>
                    <div className="text-2xl font-mono font-black text-terminal-green">${(valuationData?.median_value || 0).toFixed(2)}</div>
                </div>
            </div>

            <div className="space-y-4">
                <div className="flex justify-between items-center text-xs font-mono border-b border-white/5 pb-2">
                    <span className="text-gray-400">P25 Conservative</span>
                    <span className="text-terminal-white">${(valuationData?.p25_value || 0).toFixed(2)}</span>
                </div>
                <div className="flex justify-between items-center text-xs font-mono border-b border-white/5 pb-2">
                    <span className="text-gray-400">P75 Aggressive</span>
                    <span className="text-terminal-white">${(valuationData?.p75_value || 0).toFixed(2)}</span>
                </div>
                <div className="text-[9px] text-gray-500 font-mono leading-relaxed mt-4 italic">
                    * Results generated using 10,000 iterations of a 2-stage stochastic DCF model with Gaussian parameter distribution.
                </div>
            </div>
          </div>

          {/* Radar Chart Card */}
          <div className="p-8 bg-black/60 border border-terminal-blue/20 rounded-2xl backdrop-blur-md shadow-2xl">
            <div className="text-[10px] text-terminal-blue font-bold uppercase tracking-widest mb-1">Margin of Safety</div>
            <h3 className="text-xl font-black text-terminal-white uppercase mb-6">Institutional Pillar Strength</h3>
            <div className="flex justify-center">
                <MarginOfSafetyRadar data={valuationData.margin_of_safety} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function MarginOfSafetyRadar({ data }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!canvasRef.current || !data) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    const centerX = 200;
    const centerY = 200;
    const maxRadius = 150;

    ctx.clearRect(0, 0, 400, 400);

    const metrics = [
      { label: "FCF Yield", value: Math.min(data.fcf_yield / 10, 1), color: "#00ff88" },
      { label: "Debt/Equity", value: Math.min(1/Math.max(data.debt_to_equity, 0.1), 1), color: "#00d4ff" },
      { label: "Current Ratio", value: Math.min(data.current_ratio / 3, 1), color: "#bf5af2" },
      { label: "ROE", value: Math.min(data.roe / 30, 1), color: "#ffff00" },
      { label: "Growth", value: Math.min(data.revenue_growth / 0.2, 1), color: "#ff8800" },
    ];

    const angleStep = (2 * Math.PI) / metrics.length;

    // Grid circles
    ctx.strokeStyle = "rgba(255,255,255,0.05)";
    ctx.lineWidth = 1;
    for (let i = 1; i <= 5; i++) {
      ctx.beginPath();
      ctx.arc(centerX, centerY, (maxRadius / 5) * i, 0, 2 * Math.PI);
      ctx.stroke();
    }

    // Axes
    metrics.forEach((m, i) => {
      const angle = i * angleStep - Math.PI / 2;
      const x = centerX + maxRadius * Math.cos(angle);
      const y = centerY + maxRadius * Math.sin(angle);

      ctx.beginPath();
      ctx.moveTo(centerX, centerY);
      ctx.lineTo(x, y);
      ctx.stroke();

      // Label
      ctx.fillStyle = "rgba(255,255,255,0.4)";
      ctx.font = "bold 9px monospace";
      const labelX = centerX + (maxRadius + 30) * Math.cos(angle);
      const labelY = centerY + (maxRadius + 30) * Math.sin(angle);
      ctx.fillText(m.label, labelX - 30, labelY);
    });

    // Data polygon
    ctx.beginPath();
    metrics.forEach((m, i) => {
      const angle = i * angleStep - Math.PI / 2;
      const radius = m.value * maxRadius;
      const x = centerX + radius * Math.cos(angle);
      const y = centerY + radius * Math.sin(angle);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.closePath();
    
    // Fill with gradient
    const gradient = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, maxRadius);
    gradient.addColorStop(0, "rgba(0, 212, 255, 0.1)");
    gradient.addColorStop(1, "rgba(0, 255, 136, 0.3)");
    ctx.fillStyle = gradient;
    ctx.fill();
    
    ctx.strokeStyle = "#00ff88";
    ctx.lineWidth = 2;
    ctx.stroke();

    // Data points
    metrics.forEach((m, i) => {
        const angle = i * angleStep - Math.PI / 2;
        const radius = m.value * maxRadius;
        const x = centerX + radius * Math.cos(angle);
        const y = centerY + radius * Math.sin(angle);
        
        ctx.fillStyle = "#fff";
        ctx.beginPath();
        ctx.arc(x, y, 3, 0, Math.PI * 2);
        ctx.fill();
    });

  }, [data]);

  return <canvas ref={canvasRef} width={400} height={400} />;
}
