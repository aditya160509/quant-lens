import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://127.0.0.1:8000';

/**
 * POST /api/trades/execute - Execute a new trade
 */
export async function POST(request: NextRequest) {
    try {
        const body = await request.json();
        
        const response = await fetch(`${BACKEND_URL}/api/trades/execute`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(body),
        });

        const data = await response.json();
        
        if (!response.ok) {
            return NextResponse.json(data, { status: response.status });
        }

        return NextResponse.json(data);
    } catch (error) {
        console.error('Trade execution error:', error);
        return NextResponse.json(
            { error: 'Failed to execute trade', message: error instanceof Error ? error.message : 'Unknown error' },
            { status: 500 }
        );
    }
}
