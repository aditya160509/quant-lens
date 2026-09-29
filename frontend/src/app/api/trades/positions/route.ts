import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://127.0.0.1:8000';

/**
 * GET /api/trades/positions - Get all active positions
 */
export async function GET() {
    try {
        const response = await fetch(`${BACKEND_URL}/api/trades/positions`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        const data = await response.json();
        
        if (!response.ok) {
            return NextResponse.json(data, { status: response.status });
        }

        return NextResponse.json(data);
    } catch (error) {
        console.error('Fetch positions error:', error);
        return NextResponse.json(
            { error: 'Failed to fetch positions', message: error instanceof Error ? error.message : 'Unknown error' },
            { status: 500 }
        );
    }
}
