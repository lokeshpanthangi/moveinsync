import { useState, useEffect } from "react";
import { Sparkles, X, Minimize2, Send, Mic, Paperclip, Loader2 } from "lucide-react";
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

const API_URL = import.meta.env.VITE_API_URL;

export function MoviAssistant() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content: "Hi! I'm Movi, your AI assistant. How can I help you today?",
      timestamp: new Date(),
    },
  ]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState("");
  const [confirmationDialog, setConfirmationDialog] = useState<{
    open: boolean;
    message: string;
    consequenceInfo: any;
  }>({ open: false, message: "", consequenceInfo: null });

  // Generate session ID on mount
  useEffect(() => {
    setSessionId(`session-${Date.now()}-${Math.random().toString(36).substring(7)}`);
  }, []);

  const quickActions = [
    "Show unassigned vehicles",
    "List all vehicles",
    "How many vehicles are not assigned?",
  ];

  const handleSend = async () => {
    if (!inputValue.trim() || isLoading) return;
    
    const userMessage = inputValue;
    setInputValue("");
    
    // Add user message to chat
    setMessages(prev => [
      ...prev,
      {
        role: "user",
        content: userMessage,
        timestamp: new Date(),
      },
    ]);
    
    setIsLoading(true);
    
    try {
      // Get current page context
      const currentPath = window.location.pathname;
      let contextPage = "unknown";
      if (currentPath.includes("/buses")) contextPage = "busDashboard";
      else if (currentPath.includes("/routes")) contextPage = "routes";
      else if (currentPath.includes("/stops-paths")) contextPage = "stops_paths";
      else if (currentPath.includes("/vehicles")) contextPage = "vehicles";
      else if (currentPath.includes("/drivers")) contextPage = "drivers";
      
      // Call Movi API
      const response = await fetch(`${API_URL}/movi/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMessage,
          session_id: sessionId,
          context_page: contextPage,
        }),
      });
      
      if (!response.ok) {
        throw new Error("Failed to get response from Movi");
      }
      
      const data = await response.json();
      
      // Check if confirmation is needed (human-in-the-loop)
      if (data.awaiting_confirmation && data.consequence_info) {
        setConfirmationDialog({
          open: true,
          message: data.consequence_info.message,
          consequenceInfo: data.consequence_info,
        });
        
        // Add Movi's confirmation request to chat
        setMessages(prev => [
          ...prev,
          {
            role: "assistant",
            content: data.response,
            timestamp: new Date(),
          },
        ]);
      } else {
        // Normal response
        setMessages(prev => [
          ...prev,
          {
            role: "assistant",
            content: data.response,
            timestamp: new Date(),
          },
        ]);
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
    
    // Send user's yes/no response back to Movi
    const confirmMessage = confirmed ? "yes, proceed" : "no, cancel";
    setInputValue(confirmMessage);
    
    // Automatically send the confirmation
    setTimeout(() => handleSend(), 100);
  };

  return (
    <>
      {/* Floating Button */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="fixed bottom-6 right-6 w-16 h-16 bg-primary rounded-full shadow-lg hover:shadow-xl transition-smooth flex items-center justify-center group z-50"
        >
          <Sparkles className="w-7 h-7 text-primary-foreground animate-pulse" />
          <span className="absolute -top-1 -right-1 w-5 h-5 bg-destructive text-white text-xs rounded-full flex items-center justify-center">
            1
          </span>
        </button>
      )}

      {/* Chat Panel */}
      {isOpen && (
        <div className="fixed bottom-6 right-6 w-[400px] h-[600px] bg-card rounded-2xl shadow-2xl flex flex-col z-50 border border-border">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-border bg-primary/5 rounded-t-2xl">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-primary rounded-full flex items-center justify-center">
                <Sparkles className="w-4 h-4 text-primary-foreground" />
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
            Context: Bus Dashboard
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
                  <p className="text-sm">{message.content}</p>
                  <span className="text-xs opacity-70 mt-1 block">
                    {message.timestamp.toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>
              </div>
            ))}
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
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="icon" className="h-9 w-9 flex-shrink-0">
                <Paperclip className="w-4 h-4" />
              </Button>
              <Input
                placeholder="Ask Movi anything..."
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSend()}
                className="flex-1 bg-muted border-border"
              />
              <Button variant="ghost" size="icon" className="h-9 w-9 flex-shrink-0">
                <Mic className="w-4 h-4" />
              </Button>
              <Button
                size="icon"
                className="h-9 w-9 flex-shrink-0 bg-primary hover:bg-primary-dark"
                onClick={handleSend}
                disabled={isLoading}
              >
                {isLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
              </Button>
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
