import { NextRequest, NextResponse } from 'next/server';

const DIFY_API_KEY = process.env.DIFY_API_KEY;
const DIFY_API_BASE_URL = process.env.DIFY_API_BASE_URL || "https://api.dify.ai/v1";

export async function POST(req: NextRequest) {
  try {
    if (!DIFY_API_KEY) {
      return NextResponse.json({ error: 'Dify API key not configured' }, { status: 500 });
    }

    const formData = await req.formData();
    const file = formData.get('file') as File;
    const user = formData.get('user') as string;

    if (!file) {
      return NextResponse.json({ error: 'No file provided' }, { status: 400 });
    }

    // Create FormData for Dify API
    const difyFormData = new FormData();
    difyFormData.append('file', file);
    difyFormData.append('user', user || 'web-user');

    // Upload file to Dify
    const response = await fetch(`${DIFY_API_BASE_URL.replace(/\/$/, "")}/files/upload`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${DIFY_API_KEY}`,
      },
      body: difyFormData,
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Dify upload error:', response.status, errorText);
      return NextResponse.json(
        { error: `Upload failed: ${response.status}` }, 
        { status: response.status }
      );
    }

    const result = await response.json();
    console.log('Dify file upload successful:', result);
    return NextResponse.json(result);

  } catch (error) {
    console.error('Upload error:', error);
    return NextResponse.json(
      { error: 'Internal server error' }, 
      { status: 500 }
    );
  }
}

// Set max file size to 10MB
export const maxDuration = 60;