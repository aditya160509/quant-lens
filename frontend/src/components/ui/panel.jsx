import React from 'react';
import { cn } from "@/lib/utils";

export function Panel({ title, children, className, action }) {
    return (
        <div className={cn("flex flex-col border border-border bg-card text-card-foreground overflow-hidden", className)}>
            <div className="flex items-center justify-between bg-secondary px-2 py-1 border-b border-border">
                <h3 className="text-xs font-bold uppercase tracking-wider text-primary">{title}</h3>
                {action && <div>{action}</div>}
            </div>
            <div className="flex-1 p-2 overflow-auto relative">
                {children}
            </div>
        </div>
    );
}
