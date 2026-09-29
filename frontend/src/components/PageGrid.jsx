import React from 'react';

export default function PageGrid({ children, className = "" }) {
    return (
        <div className={`page-grid w-full h-[calc(100vh-3rem)] overflow-y-auto ${className}`}>
            {children}
        </div>
    );
}
