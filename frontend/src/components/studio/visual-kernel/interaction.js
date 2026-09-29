/**
 * Shared interaction primitives: crosshair, zoom/pan, annotations.
 */

export function hitTestCandle({ x, y, candles, scaleY, timeScale, barWidth, paddingLeft, offset }) {
    if (!candles?.length || !Number.isFinite(x)) return null;
    const idx = Math.round((x - paddingLeft) / barWidth + offset);
    if (idx < 0 || idx >= candles.length) return null;
    const c = candles[idx];
    if (!c) return null;
    return { idx, candle: c, x: timeScale(idx), yOpen: scaleY(c.open), yClose: scaleY(c.close), yHigh: scaleY(c.high), yLow: scaleY(c.low) };
}

export function drawCrosshair(ctx, { x, y, width, height, color = 'rgba(255,214,10,0.9)', label }) {
    ctx.save();
    ctx.strokeStyle = color;
    ctx.setLineDash([4, 4]);
    ctx.lineWidth = 0.8;
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
    ctx.setLineDash([]);
    if (label) {
        ctx.fillStyle = '#ffd60a';
        ctx.fillRect(x - 28, y - 10, 56, 14);
        ctx.fillStyle = '#000';
        ctx.font = '9px JetBrains Mono';
        ctx.textAlign = 'center';
        ctx.fillText(label, x, y - 1);
    }
    ctx.restore();
}

export function drawAnnotations(ctx, annotations, scaleY, timeScale) {
    annotations.forEach((a) => {
        const c = a.color || '#f59e0b';
        const w = a.width || 1.5;
        const alpha = (a.opacity ?? 100) / 100;
        ctx.save();
        ctx.globalAlpha = alpha;
        if (a.type === 'line') {
            ctx.strokeStyle = c; ctx.lineWidth = w; if (a.dash) ctx.setLineDash(a.dash);
            const y = scaleY(a.value); ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(ctx.canvas.width, y); ctx.stroke();
        } else if (a.type === 'range') {
            const y1 = scaleY(a.from); const y2 = scaleY(a.to);
            ctx.fillStyle = c; ctx.fillRect(0, Math.min(y1, y2), ctx.canvas.width, Math.abs(y2 - y1));
        } else if (a.type === 'trendline' || a.type === 'ray' || a.type === 'extended') {
            const x1 = timeScale(a.x1), y1 = scaleY(a.y1), x2 = timeScale(a.x2), y2 = scaleY(a.y2);
            ctx.strokeStyle = c; ctx.lineWidth = w; ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2);
            if (a.type === 'ray') { const dx = x2 - x1, dy = y2 - y1, len = Math.hypot(dx, dy) || 1; const ex = x2 + (dx/len)*1000, ey = y2 + (dy/len)*1000; ctx.lineTo(ex, ey); }
            if (a.type === 'extended') { const dx = x2 - x1, dy = y2 - y1, len = Math.hypot(dx, dy) || 1; const ex1 = x1 - (dx/len)*1000, ey1 = y1 - (dy/len)*1000, ex2 = x2 + (dx/len)*1000, ey2 = y2 + (dy/len)*1000; ctx.moveTo(ex1, ey1); ctx.lineTo(ex2, ey2); }
            ctx.stroke();
        } else if (a.type === 'horizontal') { const y = scaleY(a.y); ctx.strokeStyle = c; ctx.lineWidth = w; ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(ctx.canvas.width, y); ctx.stroke(); }
        else if (a.type === 'vertical') { const x = timeScale(a.x); ctx.strokeStyle = c; ctx.lineWidth = w; ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, ctx.canvas.height); ctx.stroke(); }
        else if (a.type === 'rectangle') { const x = Math.min(timeScale(a.x1), timeScale(a.x2)), y = Math.min(scaleY(a.y1), scaleY(a.y2)), ww = Math.abs(timeScale(a.x2)-timeScale(a.x1)), hh = Math.abs(scaleY(a.y2)-scaleY(a.y1)); ctx.strokeStyle = c; ctx.lineWidth = w; ctx.strokeRect(x, y, ww, hh); if (a.fill) { ctx.fillStyle = c.replace(')', `,0.15)`).replace('rgb', 'rgba'); ctx.fillRect(x, y, ww, hh); } }
        else if (a.type === 'circle') { const x = timeScale(a.x), y = scaleY(a.y), r = Math.hypot(timeScale(a.x+a.r)-x, 0); ctx.strokeStyle = c; ctx.lineWidth = w; ctx.beginPath(); ctx.arc(x, y, Math.abs(r), 0, Math.PI*2); ctx.stroke(); }
        else if (a.type === 'triangle') { const x1=timeScale(a.x1), y1=scaleY(a.y1), x2=timeScale(a.x2), y2=scaleY(a.y2), x3=timeScale(a.x3), y3=scaleY(a.y3); ctx.strokeStyle=c; ctx.lineWidth=w; ctx.beginPath(); ctx.moveTo(x1,y1); ctx.lineTo(x2,y2); ctx.lineTo(x3,y3); ctx.closePath(); ctx.stroke(); }
        else if (a.type === 'parallelChannel') { const x1=timeScale(a.x1), y1=scaleY(a.y1), x2=timeScale(a.x2), y2=scaleY(a.y2), off = a.offset || 20; ctx.strokeStyle=c; ctx.lineWidth=w; ctx.beginPath(); ctx.moveTo(x1,y1); ctx.lineTo(x2,y2); ctx.moveTo(x1,y1+off); ctx.lineTo(x2,y2+off); ctx.stroke(); }
        else if (a.type === 'fibRetracement' || a.type === 'fibExtension') { const levels = a.type==='fibRetracement' ? [0,0.236,0.382,0.5,0.618,1] : [0,0.382,0.618,1,1.382,1.618]; const x1=timeScale(a.x1), x2=timeScale(a.x2), y1=scaleY(a.y1), y2=scaleY(a.y2); levels.forEach(l=>{ const y = y1 + (y2-y1)*l; ctx.strokeStyle=c; ctx.setLineDash(l===0||l===1?[]:[4,4]); ctx.beginPath(); ctx.moveTo(x1,y); ctx.lineTo(x2,y); ctx.stroke(); ctx.fillStyle=c; ctx.font='8px JetBrains Mono'; ctx.fillText(`${(l*100).toFixed(1)}%`, x2+4, y-2); }); }
        else if (a.type === 'pitchfork') { const x1=timeScale(a.x1), y1=scaleY(a.y1), x2=timeScale(a.x2), y2=scaleY(a.y2), x3=timeScale(a.x3), y3=scaleY(a.y3); const mx=(x2+x3)/2, my=(y2+y3)/2; ctx.strokeStyle=c; ctx.lineWidth=w; ctx.beginPath(); ctx.moveTo(x1,y1); ctx.lineTo(mx,my); ctx.moveTo(x2,y2); ctx.lineTo(x2+(mx-x1), y2+(my-y1)); ctx.moveTo(x3,y3); ctx.lineTo(x3+(mx-x1), y3+(my-y1)); ctx.stroke(); }
        else if (a.type === 'gann') { const x=timeScale(a.x), y=scaleY(a.y); [1,2,3,4].forEach(k=>{ ctx.strokeStyle=c; ctx.globalAlpha=alpha* (1-k*0.15); ctx.beginPath(); ctx.moveTo(x,y); ctx.lineTo(x+100*k, y+50*k); ctx.stroke(); }); }
        else if (a.type === 'brush') { if (Array.isArray(a.points) && a.points.length>1){ ctx.strokeStyle=c; ctx.lineWidth=w; ctx.beginPath(); a.points.forEach((p,i)=>{ const x=timeScale(p.x), y=scaleY(p.y); if(i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y); }); ctx.stroke(); } }
        else if (a.type === 'text') { const x=timeScale(a.x), y=scaleY(a.y); ctx.fillStyle=c; ctx.font=`${a.size||12}px JetBrains Mono`; ctx.fillText(a.text||'', x, y); }
        else if (a.type === 'longPosition' || a.type === 'shortPosition') { const x=timeScale(a.x), y=scaleY(a.y), yy=scaleY(a.y2); const isLong=a.type==='longPosition'; ctx.fillStyle=isLong?'rgba(34,197,94,0.15)':'rgba(239,68,68,0.15)'; ctx.fillRect(x-40, Math.min(y,yy), 80, Math.abs(yy-y)); ctx.strokeStyle=c; ctx.strokeRect(x-40, Math.min(y,yy), 80, Math.abs(yy-y)); ctx.fillStyle=c; ctx.font='8px JetBrains Mono'; ctx.fillText(isLong?'LONG':'SHORT', x-16, Math.min(y,yy)-4); }
        else if (a.type === 'riskReward') { const x=timeScale(a.x), e=scaleY(a.entry), s=scaleY(a.stop), t=scaleY(a.target); ctx.fillStyle='rgba(239,68,68,0.2)'; ctx.fillRect(x-30, Math.min(e,s), 60, Math.abs(s-e)); ctx.fillStyle='rgba(34,197,94,0.2)'; ctx.fillRect(x-30, Math.min(e,t), 60, Math.abs(t-e)); ctx.strokeStyle=c; ctx.beginPath(); ctx.moveTo(x,e); ctx.lineTo(x+60,e); ctx.stroke(); }
        else if (a.type === 'measure') { const x1=timeScale(a.x1), y1=scaleY(a.y1), x2=timeScale(a.x2), y2=scaleY(a.y2); const dx=a.x2-a.x1, dy=((a.y2-a.y1)/a.y1*100).toFixed(2); ctx.strokeStyle=c; ctx.setLineDash([4,4]); ctx.beginPath(); ctx.moveTo(x1,y1); ctx.lineTo(x2,y2); ctx.stroke(); ctx.fillStyle=c; ctx.font='8px JetBrains Mono'; ctx.fillText(`${dx} bars ${dy}%`, (x1+x2)/2, (y1+y2)/2); }
        // magnet handled via hitTest snap, not draw
        ctx.restore();
    });
}

// Magnet snap to OHLC within 8px
export function magnetSnap({ x, y, candles, scaleY, timeScale, barWidth, paddingLeft, offset, enabled }) {
    if (!enabled) return { x, y };
    const hit = hitTestCandle({ x, y, candles, scaleY, timeScale, barWidth, paddingLeft, offset });
    if (!hit) return { x, y };
    const snapY = Math.abs(y - hit.yClose) < 8 ? hit.yClose : Math.abs(y - hit.yHigh) < 8 ? hit.yHigh : Math.abs(y - hit.yLow) < 8 ? hit.yLow : y;
    return { x: hit.x, y: snapY };
}
