import { NextRequest, NextResponse } from 'next/server';

const DIFY_API_KEY = process.env.DIFY_API_KEY;
const DIFY_API_BASE_URL = process.env.DIFY_API_BASE_URL || "https://api.dify.ai/v1";

// GET: Get conversations list from Dify
export async function GET(request: NextRequest) {
  if (!DIFY_API_KEY) {
    return NextResponse.json(
      { error: 'Dify API key not configured' },
      { status: 500 }
    );
  }

  const searchParams = request.nextUrl.searchParams;
  const user = searchParams.get('user');
  const lastId = searchParams.get('last_id');
  const limit = searchParams.get('limit') || '20';
  const sortBy = searchParams.get('sort_by') || '-updated_at';

  if (!user) {
    return NextResponse.json(
      { error: 'user is required' },
      { status: 400 }
    );
  }

  try {
    // Build query parameters
    const params = new URLSearchParams({
      user: user,
      limit: limit,
      sort_by: sortBy
    });
    
    if (lastId) {
      params.append('last_id', lastId);
    }

    const response = await fetch(`${DIFY_API_BASE_URL.replace(/\/$/, "")}/conversations?${params}`, {
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
        { error: 'Failed to fetch conversations from Dify API' },
        { status: response.status }
      );
    }

    const data = await response.json();
    
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching conversations:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}