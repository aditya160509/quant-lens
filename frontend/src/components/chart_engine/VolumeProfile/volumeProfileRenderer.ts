/**
 * Volume Profile Renderer
 * Canvas-based rendering for volume profile visualization
 */

import type { VolumeProfileData, VolumeProfileConfig } from './volumeProfileTypes';
import { CHART_THEME } from '../types';

// =============================================================================
// RENDER OPTIONS
// =============================================================================

export interface VolumeProfileRenderContext {
    ctx: CanvasRenderingContext2D;
    width: number;
    height: number;
    priceToY: (price: number) => number;
    visiblePriceRange: { high: number; low: number };
}

// =============================================================================
// MAIN RENDER FUNCTION
// =============================================================================

export function renderVolumeProfile(
    context: VolumeProfileRenderContext,
    profile: VolumeProfileData,
    config: VolumeProfileConfig
): void {
    const { ctx, width, height, priceToY, visiblePriceRange } = context;

    if (profile.bins.length === 0 || profile.totalVolume === 0) {
        return;
    }

    // Calculate profile render area
    const profileWidth = width * (config.width / 100);
    const xStart = config.position === 'left' ? 0 : width - profileWidth;

    // Find max volume for normalization
    const maxBinVolume = Math.max(...profile.bins.map(b => b.volume));
    if (maxBinVolume === 0) return;

    // Render each bin
    for (const bin of profile.bins) {
        // Skip bins outside visible range
        if (bin.priceHigh < visiblePriceRange.low || bin.priceLow > visiblePriceRange.high) {
            continue;
        }

        const y1 = priceToY(bin.priceHigh);
        const y2 = priceToY(bin.priceLow);
        const binHeight = Math.max(1, y2 - y1);

        // Bar width proportional to volume
        const volumeRatio = bin.volume / maxBinVolume;
        const barWidth = profileWidth * volumeRatio * 0.95;

        // Determine bar position
        const barX = config.position === 'left' 
            ? xStart 
            : xStart + profileWidth - barWidth;

        // Determine bar color
        const barColor = getBarColor(bin, volumeRatio, config);

        // Draw the bar
        ctx.fillStyle = barColor;
        ctx.globalAlpha = config.opacity;
        ctx.fillRect(barX, y1, barWidth, binHeight);
        ctx.globalAlpha = 1;

        // For up/down color scheme, render buy/sell separately
        if (config.colorScheme === 'updown' && bin.volume > 0) {
            const buyRatio = bin.buyVolume / bin.volume;
            const buyWidth = barWidth * buyRatio;
            const sellWidth = barWidth * (1 - buyRatio);

            ctx.globalAlpha = config.opacity;
            
            // Buy volume (green)
            ctx.fillStyle = CHART_THEME.upColor;
            if (config.position === 'left') {
                ctx.fillRect(barX, y1, buyWidth, binHeight);
            } else {
                ctx.fillRect(barX + sellWidth, y1, buyWidth, binHeight);
            }

            // Sell volume (red)
            ctx.fillStyle = CHART_THEME.downColor;
            if (config.position === 'left') {
                ctx.fillRect(barX + buyWidth, y1, sellWidth, binHeight);
            } else {
                ctx.fillRect(barX, y1, sellWidth, binHeight);
            }

            ctx.globalAlpha = 1;
        }
    }

    // Render POC line
    if (config.showPOC && profile.poc.binIndex >= 0) {
        const pocY = priceToY(profile.poc.price);
        
        ctx.strokeStyle = '#ff5252';
        ctx.lineWidth = 2;
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.moveTo(xStart, pocY);
        ctx.lineTo(xStart + profileWidth, pocY);
        ctx.stroke();

        // POC label
        ctx.fillStyle = '#ff5252';
        ctx.font = `bold 10px ${CHART_THEME.fontMono}`;
        ctx.textAlign = config.position === 'left' ? 'left' : 'right';
        ctx.fillText(
            `POC ${profile.poc.price.toFixed(2)}`,
            config.position === 'left' ? xStart + 4 : xStart + profileWidth - 4,
            pocY - 4
        );
    }

    // Render Value Area
    if (config.showValueArea) {
        const vahY = priceToY(profile.valueArea.high);
        const valY = priceToY(profile.valueArea.low);

        // Value Area shading
        ctx.fillStyle = 'rgba(100, 255, 218, 0.08)';
        ctx.fillRect(xStart, vahY, profileWidth, valY - vahY);

        // VAH line
        ctx.strokeStyle = CHART_THEME.accentCyan;
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(xStart, vahY);
        ctx.lineTo(xStart + profileWidth, vahY);
        ctx.stroke();

        // VAL line
        ctx.beginPath();
        ctx.moveTo(xStart, valY);
        ctx.lineTo(xStart + profileWidth, valY);
        ctx.stroke();

        ctx.setLineDash([]);

        // Labels
        ctx.fillStyle = CHART_THEME.accentCyan;
        ctx.font = `9px ${CHART_THEME.fontMono}`;
        ctx.textAlign = config.position === 'left' ? 'left' : 'right';
        const labelX = config.position === 'left' ? xStart + 4 : xStart + profileWidth - 4;
        
        ctx.fillText(`VAH ${profile.valueArea.high.toFixed(2)}`, labelX, vahY - 2);
        ctx.fillText(`VAL ${profile.valueArea.low.toFixed(2)}`, labelX, valY + 10);
    }
}

// =============================================================================
// COLOR HELPERS
// =============================================================================

function getBarColor(
    bin: { volume: number; buyVolume: number; sellVolume: number },
    volumeRatio: number,
    config: VolumeProfileConfig
): string {
    switch (config.colorScheme) {
        case 'gradient': {
            // Blue to yellow gradient based on volume
            const r = Math.round(30 + volumeRatio * 225);
            const g = Math.round(120 + volumeRatio * 90);
            const b = Math.round(200 - volumeRatio * 160);
            return `rgb(${r}, ${g}, ${b})`;
        }

        case 'updown': {
            // Mixed color based on buy/sell ratio
            if (bin.volume === 0) return CHART_THEME.textMuted;
            const buyRatio = bin.buyVolume / bin.volume;
            if (buyRatio > 0.6) return CHART_THEME.upColor;
            if (buyRatio < 0.4) return CHART_THEME.downColor;
            return '#f0a500'; // Neutral yellow
        }

        case 'single':
        default:
            return CHART_THEME.accentBlue;
    }
}

// =============================================================================
// TOOLTIP RENDERING
// =============================================================================

export function renderVolumeProfileTooltip(
    ctx: CanvasRenderingContext2D,
    profile: VolumeProfileData,
    mouseY: number,
    priceFromY: (y: number) => number,
    x: number,
    config: VolumeProfileConfig
): void {
    const mousePrice = priceFromY(mouseY);
    
    // Find the bin at mouse position
    const bin = profile.bins.find(
        b => mousePrice >= b.priceLow && mousePrice <= b.priceHigh
    );

    if (!bin) return;

    // Prepare tooltip content
    const lines = [
        `Price: ${bin.priceMiddle.toFixed(2)}`,
        `Volume: ${formatVolume(bin.volume)}`,
        `Buy: ${formatVolume(bin.buyVolume)} (${((bin.buyVolume / bin.volume) * 100).toFixed(0)}%)`,
        `Sell: ${formatVolume(bin.sellVolume)} (${((bin.sellVolume / bin.volume) * 100).toFixed(0)}%)`,
    ];

    const padding = 8;
    const lineHeight = 16;
    const tooltipWidth = 140;
    const tooltipHeight = lines.length * lineHeight + padding * 2;

    // Position tooltip
    let tooltipX = x + 10;
    let tooltipY = mouseY - tooltipHeight / 2;

    // Keep tooltip on screen
    if (tooltipX + tooltipWidth > ctx.canvas.width) {
        tooltipX = x - tooltipWidth - 10;
    }
    if (tooltipY < 0) tooltipY = 0;
    if (tooltipY + tooltipHeight > ctx.canvas.height) {
        tooltipY = ctx.canvas.height - tooltipHeight;
    }

    // Draw tooltip background
    ctx.fillStyle = 'rgba(10, 15, 24, 0.95)';
    ctx.strokeStyle = CHART_THEME.border;
    ctx.lineWidth = 1;
    
    ctx.beginPath();
    roundRect(ctx, tooltipX, tooltipY, tooltipWidth, tooltipHeight, 4);
    ctx.fill();
    ctx.stroke();

    // Draw text
    ctx.fillStyle = CHART_THEME.textPrimary;
    ctx.font = `11px ${CHART_THEME.fontMono}`;
    ctx.textAlign = 'left';

    lines.forEach((line, i) => {
        ctx.fillText(line, tooltipX + padding, tooltipY + padding + (i + 1) * lineHeight - 4);
    });
}

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

function formatVolume(volume: number): string {
    if (volume >= 1000000) {
        return (volume / 1000000).toFixed(2) + 'M';
    }
    if (volume >= 1000) {
        return (volume / 1000).toFixed(1) + 'K';
    }
    return volume.toFixed(0);
}

function roundRect(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    width: number,
    height: number,
    radius: number
): void {
    ctx.moveTo(x + radius, y);
    ctx.lineTo(x + width - radius, y);
    ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
    ctx.lineTo(x + width, y + height - radius);
    ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
    ctx.lineTo(x + radius, y + height);
    ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
    ctx.lineTo(x, y + radius);
    ctx.quadraticCurveTo(x, y, x + radius, y);
    ctx.closePath();
}

// =============================================================================
// SESSION PROFILES RENDERING
// =============================================================================

export function renderSessionProfiles(
    context: VolumeProfileRenderContext,
    sessions: Map<string, VolumeProfileData>,
    config: VolumeProfileConfig,
    timestampToX: (timestamp: number) => number
): void {
    const { ctx, priceToY, visiblePriceRange } = context;

    for (const [dateStr, profile] of sessions) {
        if (profile.bins.length === 0) continue;

        // Calculate x position for this session
        const sessionX = timestampToX(profile.startTime);
        const sessionEndX = timestampToX(profile.endTime);
        const sessionWidth = sessionEndX - sessionX;

        // Render mini profile
        renderMiniProfile(ctx, profile, {
            x: sessionX,
            width: sessionWidth * 0.3,
            priceToY,
            visiblePriceRange,
            config,
        });
    }
}

function renderMiniProfile(
    ctx: CanvasRenderingContext2D,
    profile: VolumeProfileData,
    options: {
        x: number;
        width: number;
        priceToY: (price: number) => number;
        visiblePriceRange: { high: number; low: number };
        config: VolumeProfileConfig;
    }
): void {
    const { x, width, priceToY, visiblePriceRange, config } = options;
    const maxVolume = Math.max(...profile.bins.map(b => b.volume));

    for (const bin of profile.bins) {
        if (bin.priceHigh < visiblePriceRange.low || bin.priceLow > visiblePriceRange.high) {
            continue;
        }

        const y1 = priceToY(bin.priceHigh);
        const y2 = priceToY(bin.priceLow);
        const binHeight = Math.max(1, y2 - y1);
        const barWidth = (bin.volume / maxVolume) * width;

        ctx.fillStyle = CHART_THEME.accentBlue;
        ctx.globalAlpha = config.opacity * 0.7;
        ctx.fillRect(x, y1, barWidth, binHeight);
    }

    ctx.globalAlpha = 1;

    // POC line
    const pocY = priceToY(profile.poc.price);
    ctx.strokeStyle = '#ff5252';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, pocY);
    ctx.lineTo(x + width, pocY);
    ctx.stroke();
}
