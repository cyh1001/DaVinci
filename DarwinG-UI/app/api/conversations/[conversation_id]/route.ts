import { NextRequest, NextResponse } from 'next/server';

const DIFY_API_KEY = process.env.DIFY_API_KEY;
const DIFY_API_BASE_URL = process.env.DIFY_API_BASE_URL || "https://api.dify.ai/v1";

// PATCH: Rename conversation using Dify API
export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ conversation_id: string }> }
) {
  if (!DIFY_API_KEY) {
    return NextResponse.json(
      { error: 'Dify API key not configured' },
      { status: 500 }
    );
  }

  try {
    const { conversation_id } = await params;
    const { name, user } = await request.json();
    
    if (!user || !name) {
      return NextResponse.json(
        { error: 'name and user are required' },
        { status: 400 }
      );
    }

    const response = await fetch(`${DIFY_API_BASE_URL.replace(/\/$/, "")}/conversations/${conversation_id}/name`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${DIFY_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        name: name,
        auto_generate: false,
        user: user
      })
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Dify API error:', response.status, errorText);
      return NextResponse.json(
        { error: 'Failed to rename conversation' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error renaming conversation:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

// GET: Get conversation variables (for future use)
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ conversation_id: string }> }
) {
  if (!DIFY_API_KEY) {
    return NextResponse.json(
      { error: 'Dify API key not configured' },
      { status: 500 }
    );
  }

  const { conversation_id } = await params;
  const searchParams = request.nextUrl.searchParams;
  const user = searchParams.get('user');
  const lastId = searchParams.get('last_id');
  const limit = searchParams.get('limit') || '20';
  const variableName = searchParams.get('variable_name');

  if (!user) {
    return NextResponse.json(
      { error: 'user is required' },
      { status: 400 }
    );
  }

  try {
    const queryParams = new URLSearchParams({
      user: user,
      limit: limit
    });
    
    if (lastId) queryParams.append('last_id', lastId);
    if (variableName) queryParams.append('variable_name', variableName);

    const response = await fetch(`${DIFY_API_BASE_URL.replace(/\/$/, "")}/conversations/${conversation_id}/variables?${queryParams}`, {
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
        { error: 'Failed to get conversation variables' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error getting conversation variables:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

// DELETE: Delete conversation using Dify API
export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ conversation_id: string }> }
) {
  if (!DIFY_API_KEY) {
    return NextResponse.json(
      { error: 'Dify API key not configured' },
      { status: 500 }
    );
  }

  try {
    const { conversation_id } = await params;
    const { user } = await request.json();
    
    if (!user) {
      return NextResponse.json(
        { error: 'user is required' },
        { status: 400 }
      );
    }

    const response = await fetch(`${DIFY_API_BASE_URL.replace(/\/$/, "")}/conversations/${conversation_id}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${DIFY_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        user: user
      })
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Dify API delete error:', response.status, errorText);
      return NextResponse.json(
        { error: 'Failed to delete conversation' },
        { status: response.status }
      );
    }

    // Dify returns 204 No Content on successful deletion
    return new NextResponse(null, { status: 204 });
  } catch (error) {
    console.error('Error deleting conversation:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}