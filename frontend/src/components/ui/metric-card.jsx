import React from 'react';
import { cn } from "@/lib/utils";

export function MetricCard({ label, value, change, changeType = 'percent', className }) {
    const isPositive = change > 0;
    const isNegative = change < 0;

    const colorClass = isPositive ? "text-chart-1" : isNegative ? "text-chart-2" : "text-foreground";

    return (
        <div className={cn("flex flex-col p-2 bg-card border border-border", className)}>
            <span className="text-[10px] text-muted-foreground uppercase">{label}</span>
            <div className="flex items-baseline justify-between mt-1">
                <span className="text-lg font-mono font-bold text-foreground">{value}</span>
                {change !== undefined && (
                    <span className={cn("text-xs font-mono", colorClass)}>
                        {change > 0 ? "+" : ""}{change}{changeType === 'percent' ? '%' : ''}
                    </span>
                )}
            </div>
        </div>
    );
}
