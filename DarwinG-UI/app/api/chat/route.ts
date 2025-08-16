import { openai } from "@ai-sdk/openai";
import { streamText, convertToModelMessages, type UIMessage } from "ai";

// Allow streaming responses up to 2 minutes to accommodate longer Dify runs
export const maxDuration = 120;

// Prefer Dify; fallback to OpenAI if needed.
const DIFY_API_KEY = process.env.DIFY_API_KEY;
const DIFY_API_BASE_URL = process.env.DIFY_API_BASE_URL || "https://api.dify.ai/v1";

async function canReachDify() {
  if (!DIFY_API_KEY) {
    return false;
  }
  
  // Skip connectivity check - just assume Dify is available if we have API key
  // The actual request will handle any connectivity issues
  return true;
}

export async function POST(req: Request) {
  try {
    const { messages, files }: { messages: UIMessage[], files?: any[] } = await req.json();

    let walletAddress: string | undefined;
    let conversationId: string | undefined;

    // Find the last user message and extract walletAddress, conversationId, and files from its data
    const lastUserMessage = messages.findLast((m) => m.role === "user");
    let extractedFiles: any[] = files || []; // Start with files from direct parameter
    
    if (lastUserMessage && (lastUserMessage as any).data) {
      const messageData = (lastUserMessage as any).data;
      if (typeof messageData.walletAddress === 'string') {
        walletAddress = messageData.walletAddress;
      }
      if (typeof messageData.conversationId === 'string') {
        conversationId = messageData.conversationId;
      }
      if (Array.isArray(messageData.files) && messageData.files.length > 0) {
        extractedFiles = [...extractedFiles, ...messageData.files];
        console.log("Extracted files from message data:", messageData.files);
      }
    }

    console.log("Received wallet address:", walletAddress);
    console.log("Received conversation ID:", conversationId);
    console.log("Final files to send to Dify:", extractedFiles);

    // Validate required environment variables
    if (!DIFY_API_KEY) {
      console.error("DIFY_API_KEY is not configured");
      throw new Error("AI service configuration is missing");
    }

  // Decide provider: prefer Dify; use OpenAI as fallback.
  const useDify = await canReachDify();
  
  if (useDify) {
    // Use Dify API with streaming to handle tool responses
    const lastMessage = messages[messages.length - 1];
    const query = lastMessage?.parts?.find(p => p.type === 'text')?.text || '';
    
    if (!query.trim()) {
      throw new Error("Message content is required");
    }

    // Prepare the request body according to Dify API documentation
    const requestBody: any = {
      query: query,
      inputs: {}, // Key/value pairs for app variables
      response_mode: "streaming",
      user: walletAddress || "web-user",
      auto_generate_name: true
    };

    // Add conversation_id if available
    if (conversationId) {
      requestBody.conversation_id = conversationId;
    }

    // Add files if available - validate file format according to Dify spec
    if (extractedFiles && extractedFiles.length > 0) {
      const validatedFiles = extractedFiles.filter(file => {
        // Validate required fields according to Dify documentation
        if (!file.type || !file.transfer_method) {
          console.warn("Invalid file structure - missing type or transfer_method:", file);
          return false;
        }
        
        // Validate transfer method specific requirements
        if (file.transfer_method === 'local_file' && !file.upload_file_id) {
          console.warn("Local file missing upload_file_id:", file);
          return false;
        }
        
        if (file.transfer_method === 'remote_url' && !file.url) {
          console.warn("Remote file missing URL:", file);
          return false;
        }
        
        return true;
      });
      
      if (validatedFiles.length > 0) {
        requestBody.files = validatedFiles;
        console.log("Sending validated files to Dify:", validatedFiles);
      }
    }

    console.log("Dify request body:", JSON.stringify(requestBody, null, 2));
    
    try {
      const response = await fetch(`${DIFY_API_BASE_URL.replace(/\/$/, "")}/chat-messages`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${DIFY_API_KEY}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify(requestBody)
      });

      if (!response.ok) {
        let errorMessage = 'AI service is temporarily unavailable. Please try again.';
        
        try {
          const errorData = await response.json();
          // Handle Dify API error format: { status, code, message }
          if (errorData.message) {
            errorMessage = errorData.message;
          }
          console.error('Dify API error:', errorData);
        } catch (parseError) {
          const errorText = await response.text().catch(() => 'Unknown error');
          console.error('Dify API error (text):', response.status, errorText);
        }
        
        // Customize error messages based on status codes
        if (response.status === 401 || response.status === 403) {
          errorMessage = 'Authentication failed. Please check your API configuration.';
        } else if (response.status === 429) {
          errorMessage = 'Rate limit exceeded. Please wait a moment and try again.';
        } else if (response.status === 400) {
          errorMessage = errorMessage || 'Invalid request. Please check your input and try again.';
        } else if (response.status === 404) {
          errorMessage = errorMessage || 'Conversation not found. Starting a new conversation.';
        } else if (response.status >= 500) {
          errorMessage = errorMessage || 'AI service is experiencing issues. Please try again later.';
        }
        
        // Return error as streaming response in the same format as successful responses
        return new Response(
          new ReadableStream({
            start(controller) {
              const messageId = `error_${Date.now()}`;
              
              // Send error message in streaming format compatible with useChat
              controller.enqueue(new TextEncoder().encode(`data: {"type":"start"}\\n\\n`));
              controller.enqueue(new TextEncoder().encode(`data: {"type":"start-step"}\\n\\n`));
              controller.enqueue(new TextEncoder().encode(`data: {"type":"text-start","id":"${messageId}"}\\n\\n`));
              
              const errorText = `❌ **Error:** ${errorMessage}`;
              const escapedError = JSON.stringify(errorText);
              controller.enqueue(new TextEncoder().encode(`data: {"type":"text-delta","id":"${messageId}","delta":${escapedError}}\\n\\n`));
              
              controller.enqueue(new TextEncoder().encode(`data: {"type":"text-end","id":"${messageId}"}\\n\\n`));
              controller.enqueue(new TextEncoder().encode(`data: {"type":"finish-step"}\\n\\n`));
              controller.enqueue(new TextEncoder().encode(`data: {"type":"finish"}\\n\\n`));
              controller.enqueue(new TextEncoder().encode(`data: [DONE]\\n\\n`));
              
              controller.close();
            }
          }),
          {
            headers: {
              'Content-Type': 'text/event-stream',
              'Cache-Control': 'no-cache',
              'Connection': 'keep-alive',
              'x-vercel-ai-ui-message-stream': 'v1',
            }
          }
        );
      }

      // Handle the streaming response from Dify
      return new Response(
        new ReadableStream({
          async start(controller) {
            const reader = response.body?.getReader();
            if (!reader) {
              controller.close();
              return;
            }

            let buffer = '';
            let messageId = `msg_${Date.now()}`;
            let hasStarted = false;
            let streamingContent = '';
            let capturedConversationId: string | undefined;
            let capturedTaskId: string | undefined;

            try {
              // Wait for actual content before starting message stream
              // This prevents empty assistant bubbles from appearing

              while (true) {
                let readResult;
                try {
                  readResult = await reader.read();
                } catch (readError) {
                  console.error('Stream reading error:', readError);
                  
                  if (!hasStarted) {
                    controller.enqueue(new TextEncoder().encode(`data: {"type":"text-start","id":"${messageId}"}\n\n`));
                    hasStarted = true;
                  }
                  
                  const errorText = `❌ **Connection Error:** Stream was interrupted. Please try again.`;
                  const escapedError = JSON.stringify(errorText);
                  controller.enqueue(new TextEncoder().encode(`data: {"type":"text-delta","id":"${messageId}","delta":${escapedError}}\n\n`));
                  break;
                }
                
                const { done, value } = readResult;
                if (done) break;

                buffer += new TextDecoder().decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || ''; // Keep incomplete line in buffer

                for (const line of lines) {
                  if (!line.trim()) continue;
                  
                  if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    if (data === '[DONE]') continue;
                    
                    try {
                      const parsed = JSON.parse(data);
                      // Enhanced logging and streaming for agent_log events
                      if (parsed.event === 'agent_log') {
                        const logData = parsed.data;
                        console.log("🔧 AGENT_LOG:", {
                          label: logData.label,
                          status: logData.status,
                          tool_name: logData.data?.tool_name,
                          provider: logData.metadata?.provider,
                          parent_id: logData.parent_id,
                          elapsed_time: logData.metadata?.elapsed_time
                        });
                        
                        // Stream tool execution events to client using AI SDK compatible format
                        if (logData.label && (logData.label.startsWith('CALL ') || logData.label.startsWith('ROUND ') || logData.label.includes('Thought'))) {
                          const toolData = {
                            id: logData.id,
                            name: logData.data?.tool_name || '',
                            label: logData.label,
                            status: logData.status,
                            startTime: logData.metadata?.started_at || Date.now(),
                            endTime: logData.metadata?.finished_at,
                            elapsedTime: logData.metadata?.elapsed_time,
                            provider: logData.metadata?.provider,
                            icon: logData.metadata?.icon,
                            parentId: logData.parent_id,
                            error: logData.error,
                            round: logData.label.startsWith('ROUND ') ? logData.label : undefined
                          };
                          
                          // Use AI SDK compatible data-* format
                          const toolEvent = {
                            type: "data-tool-execution",
                            data: { toolExecution: toolData }
                          };
                          
                          // Send tool event to client
                          const toolEventJson = JSON.stringify(toolEvent);
                          controller.enqueue(new TextEncoder().encode(`data: ${toolEventJson}\n\n`));
                          console.log("🚀 Sent tool event:", toolData.label, toolData.status);
                        }
                      } else if (parsed.event !== 'message') {
                        console.log("Dify stream event:", parsed.event, parsed);
                      }
                      
                      // Capture conversation_id and task_id from any response that contains them
                      if (parsed.conversation_id && !capturedConversationId) {
                        capturedConversationId = parsed.conversation_id;
                        console.log("Captured conversation ID from Dify:", capturedConversationId);
                      }
                      
                      if (parsed.task_id && !capturedTaskId) {
                        capturedTaskId = parsed.task_id;
                        console.log("Captured task ID from Dify:", capturedTaskId);
                        
                        // Store task ID but don't send it as a stream event yet
                        // We'll send it together with the actual content to avoid creating empty messages
                      }
                      
                      // Handle different Dify stream events
                      if (parsed.event === 'message' && parsed.answer) {
                        if (!hasStarted) {
                          console.log("🟢 Dify MESSAGE streaming started, task_id:", capturedTaskId);
                          // Send start sequence now that we have content
                          controller.enqueue(new TextEncoder().encode(`data: {"type":"start"}\n\n`));
                          controller.enqueue(new TextEncoder().encode(`data: {"type":"start-step"}\n\n`));
                          controller.enqueue(new TextEncoder().encode(`data: {"type":"text-start","id":"${messageId}"}\n\n`));
                          
                          // Now send task ID with the content to enable stop functionality
                          if (capturedTaskId) {
                            controller.enqueue(new TextEncoder().encode(`data: {"type":"data-task-id","data":{"taskId":"${capturedTaskId}"}}\n\n`));
                          }
                          
                          hasStarted = true;
                        }
                        
                        // Stream each message chunk immediately with proper JSON escaping
                        const escapedAnswer = JSON.stringify(parsed.answer);
                        controller.enqueue(new TextEncoder().encode(`data: {"type":"text-delta","id":"${messageId}","delta":${escapedAnswer}}\n\n`));
                        streamingContent += parsed.answer;
                      }
                      
                      // Handle agent_log events with streaming output
                      else if (parsed.event === 'agent_log' && parsed.data && parsed.data.data && parsed.data.data.output && parsed.data.status === 'success') {
                        const output = parsed.data.data.output;
                        if (typeof output === 'string' && output.trim()) {
                          if (!hasStarted) {
                            console.log("🟢 Dify AGENT_LOG streaming started, task_id:", capturedTaskId);
                            console.log("🟢 Agent output content:", output.substring(0, 100) + (output.length > 100 ? '...' : ''));
                            // Send start sequence now that we have content
                            controller.enqueue(new TextEncoder().encode(`data: {"type":"start"}\n\n`));
                            controller.enqueue(new TextEncoder().encode(`data: {"type":"start-step"}\n\n`));
                            controller.enqueue(new TextEncoder().encode(`data: {"type":"text-start","id":"${messageId}"}\n\n`));
                            
                            // Now send task ID with the content to enable stop functionality
                            if (capturedTaskId) {
                              controller.enqueue(new TextEncoder().encode(`data: {"type":"data-task-id","data":{"taskId":"${capturedTaskId}"}}\n\n`));
                            }
                            
                            hasStarted = true;
                          }
                          
                          // Only stream new content that we haven't seen before
                          if (output.length > streamingContent.length && output.startsWith(streamingContent)) {
                            const newContent = output.substring(streamingContent.length);
                            const escapedNewContent = JSON.stringify(newContent);
                            controller.enqueue(new TextEncoder().encode(`data: {"type":"text-delta","id":"${messageId}","delta":${escapedNewContent}}\n\n`));
                            streamingContent = output;
                          } else if (streamingContent.length === 0) {
                            // First chunk of content
                            const escapedOutput = JSON.stringify(output);
                            controller.enqueue(new TextEncoder().encode(`data: {"type":"text-delta","id":"${messageId}","delta":${escapedOutput}}\n\n`));
                            streamingContent = output;
                          }
                        }
                      }
                      
                      // Handle error events from Dify - check various error conditions
                      else if (
                        parsed.event === 'error' || 
                        parsed.event === 'message_end' && parsed.metadata && parsed.metadata.error ||
                        parsed.event === 'workflow_finished' && parsed.data && parsed.data.status === 'failed' ||
                        parsed.status === 'failed' ||
                        (parsed.data && parsed.data.error) ||
                        (parsed.error)
                      ) {
                        console.log("Detected Dify error event:", parsed);
                        
                        let errorMessage = 'An error occurred during processing';
                        
                        if (parsed.message) errorMessage = parsed.message;
                        else if (parsed.metadata?.error?.message) errorMessage = parsed.metadata.error.message;
                        else if (parsed.data?.error?.message) errorMessage = parsed.data.error.message;
                        else if (parsed.error?.message) errorMessage = parsed.error.message;
                        else if (parsed.data?.error) errorMessage = String(parsed.data.error);
                        else if (parsed.error) errorMessage = String(parsed.error);
                        
                        if (!hasStarted) {
                          controller.enqueue(new TextEncoder().encode(`data: {"type":"text-start","id":"${messageId}"}\n\n`));
                          hasStarted = true;
                        }
                        
                        const errorText = `\n❌ Error: ${errorMessage}`;
                        const escapedError = JSON.stringify(errorText);
                        controller.enqueue(new TextEncoder().encode(`data: {"type":"text-delta","id":"${messageId}","delta":${escapedError}}\n\n`));
                        
                        // End the stream on error
                        controller.enqueue(new TextEncoder().encode(`data: {"type":"text-end","id":"${messageId}"}\n\n`));
                        controller.enqueue(new TextEncoder().encode(`data: {"type":"finish-step"}\n\n`));
                        controller.enqueue(new TextEncoder().encode(`data: {"type":"finish"}\n\n`));
                        controller.enqueue(new TextEncoder().encode(`data: [DONE]\n\n`));
                        controller.close();
                        return;
                      }
                      
                      // Also handle workflow_finished as backup for complete response
                      else if (parsed.event === 'workflow_finished') {
                        if (parsed.data && parsed.data.outputs && parsed.data.outputs.answer) {
                          const completeResponse = parsed.data.outputs.answer;
                          
                          // If we have more content than what was streamed, send the rest
                          if (completeResponse.length > streamingContent.length) {
                            const remainingContent = completeResponse.substring(streamingContent.length);
                            if (remainingContent.trim()) {
                              if (!hasStarted) {
                                controller.enqueue(new TextEncoder().encode(`data: {"type":"text-start","id":"${messageId}"}\n\n`));
                                hasStarted = true;
                              }
                              const escapedRemaining = JSON.stringify(remainingContent);
                              controller.enqueue(new TextEncoder().encode(`data: {"type":"text-delta","id":"${messageId}","delta":${escapedRemaining}}\n\n`));
                            }
                          }
                        }
                        
                        // End the message and stream
                        if (hasStarted) {
                          controller.enqueue(new TextEncoder().encode(`data: {"type":"text-end","id":"${messageId}"}\n\n`));
                        }
                        
                        // Include conversation_id in the final message metadata
                        if (capturedConversationId) {
                          // Use AI SDK-compatible data-* event with data payload
                          controller.enqueue(new TextEncoder().encode(`data: {"type":"data-conversation-id","data":{"conversationId":"${capturedConversationId}"}}\n\n`));
                        }
                        
                        controller.enqueue(new TextEncoder().encode(`data: {"type":"finish-step"}\n\n`));
                        controller.enqueue(new TextEncoder().encode(`data: {"type":"finish"}\n\n`));
                        controller.enqueue(new TextEncoder().encode(`data: [DONE]\n\n`));
                        
                        controller.close();
                        return;
                      }
                    } catch (e) {
                      // Skip malformed JSON
                      continue;
                    }
                  }
                }
              }
              
              // Fallback if connection ends without workflow_finished
              if (hasStarted) {
                console.log('Dify stream completed normally');
                controller.enqueue(new TextEncoder().encode(`data: {"type":"text-end","id":"${messageId}"}\n\n`));
              } else {
                // No content was received at all, show error message
                console.log('No content received from Dify, sending error message');
                // Send start sequence for error message
                controller.enqueue(new TextEncoder().encode(`data: {"type":"start"}\n\n`));
                controller.enqueue(new TextEncoder().encode(`data: {"type":"start-step"}\n\n`));
                controller.enqueue(new TextEncoder().encode(`data: {"type":"text-start","id":"${messageId}"}\n\n`));
                const errorText = `\n❌ Error: The AI service didn't provide a response. Please try again.`;
                const escapedError = JSON.stringify(errorText);
                controller.enqueue(new TextEncoder().encode(`data: {"type":"text-delta","id":"${messageId}","delta":${escapedError}}\n\n`));
                controller.enqueue(new TextEncoder().encode(`data: {"type":"text-end","id":"${messageId}"}\n\n`));
              }
              
              // Include conversation_id in the final message metadata
              if (capturedConversationId) {
                // Use AI SDK-compatible data-* event with data payload
                controller.enqueue(new TextEncoder().encode(`data: {"type":"data-conversation-id","data":{"conversationId":"${capturedConversationId}"}}\n\n`));
              }
              
              controller.enqueue(new TextEncoder().encode(`data: {"type":"finish-step"}\n\n`));
              controller.enqueue(new TextEncoder().encode(`data: {"type":"finish"}\n\n`));
              controller.enqueue(new TextEncoder().encode(`data: [DONE]\n\n`));
              
            } catch (streamError) {
              console.error('Streaming error:', streamError);
              
              // Send error message if stream fails
              if (!hasStarted) {
                controller.enqueue(new TextEncoder().encode(`data: {"type":"text-start","id":"${messageId}"}\n\n`));
              }
              
              const errorText = `❌ **Stream Error:** Connection to AI service failed. Please try again.`;
              const escapedError = JSON.stringify(errorText);
              controller.enqueue(new TextEncoder().encode(`data: {"type":"text-delta","id":"${messageId}","delta":${escapedError}}\n\n`));
              
              if (!hasStarted) {
                controller.enqueue(new TextEncoder().encode(`data: {"type":"text-end","id":"${messageId}"}\n\n`));
              }
              
              controller.enqueue(new TextEncoder().encode(`data: {"type":"finish-step"}\n\n`));
              controller.enqueue(new TextEncoder().encode(`data: {"type":"finish"}\n\n`));
              controller.enqueue(new TextEncoder().encode(`data: [DONE]\n\n`));
              
            } finally {
              reader.releaseLock();
            }
          }
        }),
        {
          headers: {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'x-vercel-ai-ui-message-stream': 'v1',
          }
        }
      );

    } catch (error) {
      console.error('Dify API failed:', error);
      // Fall through to OpenAI fallback
    }
  }

  // Fallback to OpenAI
  try {
    console.log("Using OpenAI fallback");
    const result = streamText({
      model: openai("gpt-4o-mini"),
      messages: convertToModelMessages(messages),
    });

    return result.toUIMessageStreamResponse();
  } catch (openaiError) {
    console.error('OpenAI fallback also failed:', openaiError);
    
    // Return a proper error response
    return new Response(
      JSON.stringify({
        error: 'Both AI services are currently unavailable. Please try again later.',
        details: openaiError instanceof Error ? openaiError.message : 'Unknown error'
      }),
      {
        status: 500,
        headers: {
          'Content-Type': 'application/json',
        }
      }
    );
  }

  } catch (requestError) {
    console.error('Request processing error:', requestError);
    
    return new Response(
      JSON.stringify({
        error: 'Failed to process request. Please check your input and try again.',
        details: requestError instanceof Error ? requestError.message : 'Unknown error'
      }),
      {
        status: 400,
        headers: {
          'Content-Type': 'application/json',
        }
      }
    );
  }
}
