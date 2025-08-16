import { NextRequest, NextResponse } from 'next/server';
import type { DifyHistoryResponse } from '@/lib/conversation';

const DIFY_API_KEY = process.env.DIFY_API_KEY;
const DIFY_API_BASE_URL = process.env.DIFY_API_BASE_URL || "https://api.dify.ai/v1";

export async function GET(request: NextRequest) {
  if (!DIFY_API_KEY) {
    return NextResponse.json(
      { error: 'Dify API key not configured' },
      { status: 500 }
    );
  }

  const searchParams = request.nextUrl.searchParams;
  const conversationId = searchParams.get('conversation_id');
  const user = searchParams.get('user');
  const firstId = searchParams.get('first_id');
  const limit = searchParams.get('limit') || '20';

  if (!conversationId || !user) {
    return NextResponse.json(
      { error: 'conversation_id and user are required' },
      { status: 400 }
    );
  }

  try {
    // Build query parameters
    const params = new URLSearchParams({
      conversation_id: conversationId,
      user: user,
      limit: limit
    });
    
    if (firstId) {
      params.append('first_id', firstId);
    }

    const response = await fetch(`${DIFY_API_BASE_URL.replace(/\/$/, "")}/messages?${params}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${DIFY_API_KEY}`,
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Dify API error:', response.status, errorText);
      return NextResponse.json(
        { error: 'Failed to fetch messages from Dify API' },
        { status: response.status }
      );
    }

    const data: DifyHistoryResponse = await response.json();
    
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching conversation history:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}