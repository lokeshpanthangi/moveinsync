import { useState, useEffect, useRef } from "react";
import { Bot, X, Minimize2, Send, Mic, MicOff, Image as ImageIcon, XCircle, Loader2, Volume2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github-dark.css";
import { useVoiceChat } from "@/hooks/useVoiceChat";
import ShinyText from "@/components/ui/ShinyText";

const API_URL = import.meta.env.VITE_API_URL;

interface Message {
  role: "assistant" | "user";
  content: string;
  timestamp: Date;
  image?: string; // Base64 image data
}

export function MoviAssistant() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: "Hi! I'm Movi, your AI assistant. How can I help you today?",
      timestamp: new Date(),
    },
  ]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState("");
  const [contextPage, setContextPage] = useState("unknown");
  const [confirmationDialog, setConfirmationDialog] = useState<{
    open: boolean;
    message: string;
    consequenceInfo: any;
  }>({ open: false, message: "", consequenceInfo: null });

  // Voice mode state
  const [voiceMode, setVoiceMode] = useState(false);

  // Image upload state
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Voice chat hook - always call (never conditionally)
  const voiceChat = useVoiceChat({
    sessionId: sessionId || '', // Pass empty string if not ready, hook will handle it
    contextPage,
    onError: (error) => {
      console.error("Voice error:", error);
      setMessages(prev => [
        ...prev,
        {
          role: "assistant",
          content: `Voice error: ${error}`,
          timestamp: new Date(),
        },
      ]);
    }
  });

  // Generate session ID on mount
  useEffect(() => {
    setSessionId(`session-${Date.now()}-${Math.random().toString(36).substring(7)}`);
  }, []);

  // Sync voice messages with main messages
  useEffect(() => {
    if (voiceMode && sessionId && voiceChat.messages.length > 0) {
      // Convert voice messages to main message format
      const lastVoiceMessage = voiceChat.messages[voiceChat.messages.length - 1];
      const lastMainMessage = messages[messages.length - 1];

      // Only add if it's a new message
      if (!lastMainMessage || lastVoiceMessage.timestamp > lastMainMessage.timestamp) {
        setMessages(prev => [...prev, {
          role: lastVoiceMessage.type,
          content: lastVoiceMessage.text,
          timestamp: lastVoiceMessage.timestamp
        }]);
      }
    }
  }, [voiceChat.messages, voiceMode, sessionId]);

  // Handle voice confirmation dialog
  useEffect(() => {
    if (sessionId && voiceChat.requiresConfirmation && voiceChat.consequenceInfo) {
      setConfirmationDialog({
        open: true,
        message: voiceChat.consequenceInfo.message,
        consequenceInfo: voiceChat.consequenceInfo
      });
    }
  }, [voiceChat.requiresConfirmation, voiceChat.consequenceInfo, sessionId]);

  // Detect current page context
  useEffect(() => {
    const currentPath = window.location.pathname;
    let page = "unknown";
    if (currentPath.includes("/buses")) page = "busDashboard";
    else if (currentPath.includes("/routes")) page = "routes";
    else if (currentPath.includes("/stops-paths")) page = "stops_paths";
    else if (currentPath.includes("/vehicles")) page = "vehicles";
    else if (currentPath.includes("/drivers")) page = "drivers";
    setContextPage(page);
  }, []);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Handle image paste from clipboard (ChatGPT-style)
  useEffect(() => {
    const handlePaste = (e: ClipboardEvent) => {
      if (!isOpen) return;

      const items = e.clipboardData?.items;
      if (!items) return;

      for (let i = 0; i < items.length; i++) {
        if (items[i].type.indexOf("image") !== -1) {
          e.preventDefault();
          const blob = items[i].getAsFile();
          if (blob) {
            handleImageFile(blob);
          }
          break;
        }
      }
    };

    document.addEventListener("paste", handlePaste);
    return () => document.removeEventListener("paste", handlePaste);
  }, [isOpen]);

  // Convert image file to base64
  const handleImageFile = (file: File) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const base64String = reader.result as string;
      setSelectedImage(base64String);
      setImagePreview(base64String);
    };
    reader.readAsDataURL(file);
  };

  // Handle file input change
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && file.type.startsWith("image/")) {
      handleImageFile(file);
    }
  };

  // Remove selected image
  const removeImage = () => {
    setSelectedImage(null);
    setImagePreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const quickActions = [
    "Show unassigned vehicles",
    "List all vehicles",
    "How many vehicles are not assigned?",
  ];

  const handleSend = async () => {
    if ((!inputValue.trim() && !selectedImage) || isLoading) return;

    const userMessage = inputValue || "What's in this image?";
    const imageToSend = selectedImage;

    setInputValue("");

    // Add user message to chat with image
    setMessages(prev => [
      ...prev,
      {
        role: "user",
        content: userMessage,
        timestamp: new Date(),
        image: imageToSend || undefined,
      },
    ]);

    // Clear image after adding to chat
    setSelectedImage(null);
    setImagePreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }

    setIsLoading(true);

    try {
      // Prepare request body
      const requestBody: any = {
        message: userMessage,
        session_id: sessionId,
        context_page: contextPage,
      };

      // Add image if present (extract base64 data)
      if (imageToSend) {
        // Remove data:image/xxx;base64, prefix if present
        const base64Data = imageToSend.includes("base64,")
          ? imageToSend.split("base64,")[1]
          : imageToSend;
        requestBody.image_base64 = base64Data;
      }

      // Call Movi API
      const response = await fetch(`${API_URL}/movi/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        throw new Error("Failed to get response from Movi");
      }

      // Create a placeholder message for the assistant response
      setMessages(prev => [
        ...prev,
        {
          role: "assistant",
          content: "",
          timestamp: new Date(),
        },
      ]);

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) throw new Error("No reader available");

      let accumulatedResponse = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (!line.trim()) continue;

          try {
            const data = JSON.parse(line);

            if (data.type === "token") {
              accumulatedResponse += data.content;

              // Update the last message with new content
              setMessages(prev => {
                const newMessages = [...prev];
                const lastMsg = newMessages[newMessages.length - 1];
                if (lastMsg.role === "assistant") {
                  lastMsg.content = accumulatedResponse;
                }
                return newMessages;
              });
            }
            else if (data.type === "confirmation") {
              // Handle HITL confirmation
              setConfirmationDialog({
                open: true,
                message: data.payload.message,
                consequenceInfo: data.payload,
              });
            }
            else if (data.type === "error") {
              console.error("Stream error:", data.content);
              // Optionally show error in chat
            }
          } catch (e) {
            console.error("Error parsing stream line:", line, e);
          }
        }
      }

    } catch (error) {
      console.error("Error calling Movi:", error);
      setMessages(prev => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, I encountered an error. Please try again.",
          timestamp: new Date(),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleConfirmAction = async (confirmed: boolean) => {
    setConfirmationDialog({ open: false, message: "", consequenceInfo: null });

    // If in voice mode, use voice chat confirmation
    if (voiceMode) {
      await voiceChat.sendConfirmation(confirmed);
      return;
    }

    // Text mode confirmation
    const confirmMessage = confirmed ? "yes" : "no";

    // Add user's confirmation message to chat
    setMessages(prev => [
      ...prev,
      {
        role: "user",
        content: confirmMessage,
        timestamp: new Date(),
      },
    ]);

    setIsLoading(true);

    try {
      // Send confirmation directly to backend
      const response = await fetch(`${API_URL}/movi/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: confirmMessage,
          session_id: sessionId,
          context_page: contextPage,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to get response from Movi");
      }

      // Create a placeholder message for the assistant response
      setMessages(prev => [
        ...prev,
        {
          role: "assistant",
          content: "",
          timestamp: new Date(),
        },
      ]);

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) throw new Error("No reader available");

      let accumulatedResponse = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (!line.trim()) continue;

          try {
            const data = JSON.parse(line);

            if (data.type === "token") {
              accumulatedResponse += data.content;

              // Update the last message with new content
              setMessages(prev => {
                const newMessages = [...prev];
                const lastMsg = newMessages[newMessages.length - 1];
                if (lastMsg.role === "assistant") {
                  lastMsg.content = accumulatedResponse;
                }
                return newMessages;
              });
            }
            else if (data.type === "error") {
              console.error("Stream error:", data.content);
            }
          } catch (e) {
            console.error("Error parsing stream line:", line, e);
          }
        }
      }
    } catch (error) {
      console.error("Error sending confirmation:", error);
      setMessages(prev => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, I encountered an error processing your confirmation.",
          timestamp: new Date(),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      {/* Floating Button */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="fixed bottom-6 right-6 w-16 h-16 bg-primary rounded-full shadow-lg hover:shadow-xl hover:scale-110 transition-all duration-300 flex items-center justify-center group z-50 animate-in fade-in zoom-in"
        >
          <Bot className="w-7 h-7 text-primary-foreground" />
        </button>
      )}

      {/* Chat Panel */}
      {isOpen && (
        <div className="fixed bottom-6 right-6 w-[400px] h-[600px] bg-card rounded-2xl shadow-2xl flex flex-col z-50 border border-border animate-in slide-in-from-bottom-4 slide-in-from-right-4 fade-in duration-300">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-border bg-primary/5 rounded-t-2xl">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-primary rounded-full flex items-center justify-center">
                <Bot className="w-4 h-4 text-primary-foreground" />
              </div>
              <div>
                <h3 className="font-semibold text-foreground">Movi</h3>
                <p className="text-xs text-muted-foreground">AI Assistant</p>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => setIsOpen(false)}
              >
                <Minimize2 className="w-4 h-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => setIsOpen(false)}
              >
                <X className="w-4 h-4" />
              </Button>
            </div>
          </div>

          {/* Context Indicator */}
          <div className="px-4 py-2 bg-muted/50 text-xs text-muted-foreground border-b border-border">
            Context: {
              contextPage === "busDashboard" ? "Bus Dashboard (Trips, Vehicles, Drivers)" :
                contextPage === "routes" ? "Routes (Route Management)" :
                  contextPage === "stops_paths" ? "Stops & Paths (Stop & Path Configuration)" :
                    contextPage === "vehicles" ? "Vehicles (Vehicle Management)" :
                      contextPage === "drivers" ? "Drivers (Driver Management)" :
                        "General"
            }
          </div>

          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.map((message, index) => (
              <div
                key={index}
                className={cn(
                  "flex",
                  message.role === "user" ? "justify-end" : "justify-start"
                )}
              >
                <div
                  className={cn(
                    "max-w-[80%] rounded-2xl px-4 py-2.5",
                    message.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-foreground"
                  )}
                >
                  {/* Show image if present */}
                  {message.image && (
                    <img
                      src={message.image}
                      alt="Uploaded content"
                      className="rounded-lg mb-2 max-w-full h-auto max-h-48 object-contain"
                    />
                  )}
                  {/* Render markdown for assistant messages, plain text for user */}
                  {message.role === "assistant" ? (
                    message.content ? (
                      <div className="chat-markdown">
                        <ReactMarkdown
                          rehypePlugins={[rehypeHighlight]}
                          components={{
                            code: ({ node, inline, className, children, ...props }: any) => {
                              return inline ? (
                                <code className="bg-muted/50 px-1.5 py-0.5 rounded text-xs font-mono border border-border" {...props}>
                                  {children}
                                </code>
                              ) : (
                                <code className={className} {...props}>
                                  {children}
                                </code>
                              );
                            },
                          }}
                        >
                          {message.content}
                        </ReactMarkdown>
                      </div>
                    ) : (
                      <ShinyText text="Thinking..." speed={3} />
                    )
                  ) : (
                    <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                  )}
                  <span className="text-xs opacity-70 mt-1 block">
                    {message.timestamp.toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* Quick Actions */}
          {messages.length === 1 && (
            <div className="px-4 pb-3 space-y-2">
              {quickActions.map((action, index) => (
                <button
                  key={index}
                  onClick={() => setInputValue(action)}
                  className="w-full text-left text-sm px-3 py-2 bg-muted hover:bg-muted/80 rounded-lg transition-fast text-foreground"
                >
                  {action}
                </button>
              ))}
            </div>
          )}

          {/* Input Area */}
          <div className="p-4 border-t border-border">
            {/* Voice Mode Indicator */}
            {voiceMode && (
              <div className="mb-3 p-3 bg-primary/10 border border-primary/30 rounded-lg">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {voiceChat.isRecording && (
                      <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse" />
                    )}
                    {voiceChat.isProcessing && (
                      <Loader2 className="w-4 h-4 animate-spin text-primary" />
                    )}
                    {voiceChat.isSpeaking && (
                      <Volume2 className="w-4 h-4 text-primary animate-pulse" />
                    )}
                    <span className="text-sm font-medium">
                      {voiceChat.isRecording ? "🎤 Listening..." :
                        voiceChat.isProcessing ? "⏳ Processing..." :
                          voiceChat.isSpeaking ? "🔊 Speaking..." :
                            "Voice Mode Active"}
                    </span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setVoiceMode(false);
                      voiceChat.stopRecording();
                      voiceChat.stopAudio();
                    }}
                  >
                    Exit Voice Mode
                  </Button>
                </div>
              </div>
            )}

            {/* Image Preview (only in text mode) */}
            {!voiceMode && imagePreview && (
              <div className="mb-3 relative inline-block">
                <img
                  src={imagePreview}
                  alt="Preview"
                  className="rounded-lg max-h-32 object-contain border-2 border-primary"
                />
                <button
                  onClick={removeImage}
                  className="absolute -top-2 -right-2 bg-destructive text-white rounded-full p-1 hover:bg-destructive/90 transition-colors"
                >
                  <XCircle className="w-4 h-4" />
                </button>
              </div>
            )}

            <div className="flex items-center gap-2">
              {!voiceMode ? (
                <>
                  {/* Text Mode Controls */}
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    onChange={handleFileSelect}
                    className="hidden"
                  />

                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-9 w-9 flex-shrink-0"
                    onClick={() => fileInputRef.current?.click()}
                    title="Upload image"
                  >
                    <ImageIcon className="w-4 h-4" />
                  </Button>

                  <Input
                    ref={inputRef}
                    placeholder="Ask Movi anything... (Paste images with Ctrl+V)"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
                    className="flex-1 bg-muted border-border"
                  />

                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-9 w-9 flex-shrink-0"
                    onClick={() => {
                      if (!sessionId) {
                        console.warn('⚠️ Session not ready yet');
                        return;
                      }
                      setVoiceMode(true);
                    }}
                    disabled={!sessionId}
                    title={sessionId ? "Switch to voice mode" : "Initializing..."}
                  >
                    <Mic className="w-4 h-4" />
                  </Button>

                  <Button
                    size="icon"
                    className="h-9 w-9 flex-shrink-0 bg-primary hover:bg-primary-dark"
                    onClick={handleSend}
                    disabled={isLoading || (!inputValue.trim() && !selectedImage)}
                  >
                    {isLoading ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Send className="w-4 h-4" />
                    )}
                  </Button>
                </>
              ) : (
                <>
                  {/* Voice Mode Controls */}
                  <div className="flex-1 flex items-center justify-center">
                    <Button
                      size="lg"
                      className={cn(
                        "h-16 w-16 rounded-full transition-all",
                        voiceChat.isRecording
                          ? "bg-red-500 hover:bg-red-600 animate-pulse"
                          : "bg-primary hover:bg-primary-dark"
                      )}
                      onClick={() => {
                        if (voiceChat.isRecording) {
                          voiceChat.stopRecording();
                        } else {
                          voiceChat.startRecording();
                        }
                      }}
                      disabled={voiceChat.isProcessing || voiceChat.isSpeaking}
                    >
                      {voiceChat.isRecording ? (
                        <MicOff className="w-6 h-6" />
                      ) : (
                        <Mic className="w-6 h-6" />
                      )}
                    </Button>
                  </div>

                  {voiceChat.isSpeaking && (
                    <Button
                      variant="outline"
                      size="icon"
                      className="h-9 w-9"
                      onClick={() => voiceChat.stopAudio()}
                      title="Stop speaking"
                    >
                      <X className="w-4 h-4" />
                    </Button>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Dialog for Human-in-the-Loop */}
      <AlertDialog open={confirmationDialog.open} onOpenChange={(open) =>
        !open && setConfirmationDialog({ open: false, message: "", consequenceInfo: null })
      }>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>⚠️ Confirmation Required</AlertDialogTitle>
            <AlertDialogDescription>
              {confirmationDialog.message}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => handleConfirmAction(false)}>
              No, Cancel
            </AlertDialogCancel>
            <AlertDialogAction onClick={() => handleConfirmAction(true)}>
              Yes, Proceed
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
