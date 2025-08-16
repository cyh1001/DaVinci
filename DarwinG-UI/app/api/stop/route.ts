import { NextRequest, NextResponse } from 'next/server';

const DIFY_API_KEY = process.env.DIFY_API_KEY;
const DIFY_API_BASE_URL = process.env.DIFY_API_BASE_URL || "https://api.dify.ai/v1";

export async function POST(req: NextRequest) {
  try {
    if (!DIFY_API_KEY) {
      return NextResponse.json({ error: 'Dify API key not configured' }, { status: 500 });
    }

    const body = await req.json();
    const { task_id, user } = body;

    if (!task_id) {
      return NextResponse.json({ error: 'task_id is required' }, { status: 400 });
    }

    if (!user) {
      return NextResponse.json({ error: 'user is required' }, { status: 400 });
    }

    console.log('Stopping generation for task:', task_id, 'user:', user);

    // Call Dify API to stop generation
    const response = await fetch(`${DIFY_API_BASE_URL.replace(/\/$/, "")}/chat-messages/${task_id}/stop`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${DIFY_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user: user
      })
    });

    if (!response.ok) {
      const errorText = await response.text().catch(() => 'Unknown error');
      console.error('Dify stop API error:', response.status, errorText);
      return NextResponse.json(
        { error: `Stop failed: ${response.status}` }, 
        { status: response.status }
      );
    }

    const result = await response.json();
    console.log('Generation stopped successfully:', result);
    
    return NextResponse.json(result);

  } catch (error) {
    console.error('Stop generation error:', error);
    return NextResponse.json(
      { error: 'Failed to stop generation' }, 
      { status: 500 }
    );
  }
}