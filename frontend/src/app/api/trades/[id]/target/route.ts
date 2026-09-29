import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://127.0.0.1:8000';

/**
 * PATCH /api/trades/[id]/target - Modify take profit
 */
export async function PATCH(
    request: NextRequest,
    { params }: { params: Promise<{ id: string }> }
) {
    try {
        const { id } = await params;
        const body = await request.json();
        
        const response = await fetch(`${BACKEND_URL}/api/trades/${id}/target`, {
            method: 'PATCH',
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
        console.error('Modify take profit error:', error);
        return NextResponse.json(
            { error: 'Failed to modify take profit', message: error instanceof Error ? error.message : 'Unknown error' },
            { status: 500 }
        );
    }
}
