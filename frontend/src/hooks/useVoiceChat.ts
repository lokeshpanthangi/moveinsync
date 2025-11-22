import { useState, useEffect, useRef, useCallback } from 'react';

const API_URL = import.meta.env.VITE_API_URL;

interface VoiceMessage {
  type: 'user' | 'assistant';
  text: string;
  timestamp: Date;
  audio?: string; // Base64 audio for assistant responses
}

interface UseVoiceChatOptions {
  sessionId: string;
  contextPage: string;
  onError?: (error: string) => void;
}

export function useVoiceChat({ sessionId, contextPage, onError }: UseVoiceChatOptions) {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [messages, setMessages] = useState<VoiceMessage[]>([]);
  const [requiresConfirmation, setRequiresConfirmation] = useState(false);
  const [consequenceInfo, setConsequenceInfo] = useState<any>(null);
  
  const wsRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioContextRef = useRef<AudioContext | null>(null);
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);

  // Initialize WebSocket connection
  const connectWebSocket = useCallback(() => {
    // Guard against empty sessionId
    if (!sessionId || sessionId.trim() === '') {
      console.warn('⚠️ Cannot connect WebSocket without valid session ID');
      return;
    }
    
    const wsUrl = API_URL.replace('http', 'ws') + '/movi/voice';
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('🎤 Voice WebSocket connected');
      // Send initialization message
      ws.send(JSON.stringify({
        type: 'init',
        session_id: sessionId,
        context_page: contextPage
      }));
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'ready') {
        console.log('✅ Voice session ready');
      } else if (data.type === 'transcription') {
        console.log('📝 Transcription:', data.text);
        // Add user message to chat
        setMessages(prev => [...prev, {
          type: 'user',
          text: data.text,
          timestamp: new Date()
        }]);
      } else if (data.type === 'audio_response') {
        console.log('🔊 Received audio response');
        setIsProcessing(false);
        
        // Add assistant message to chat
        setMessages(prev => [...prev, {
          type: 'assistant',
          text: data.text,
          timestamp: new Date(),
          audio: data.data
        }]);
        
        // Check for confirmation requirement
        if (data.awaiting_confirmation && data.consequence_info) {
          setRequiresConfirmation(true);
          setConsequenceInfo(data.consequence_info);
        }
        
        // Play audio response
        playAudio(data.data);
      } else if (data.type === 'error') {
        console.error('❌ Voice error:', data.message);
        setIsProcessing(false);
        onError?.(data.message);
      }
    };

    ws.onerror = (error) => {
      console.error('❌ WebSocket error:', error);
      onError?.('Voice connection error');
    };

    ws.onclose = () => {
      console.log('🔌 Voice WebSocket disconnected');
    };

    wsRef.current = ws;
  }, [sessionId, contextPage, onError]);

  // Initialize on mount
  useEffect(() => {
    // Only connect if sessionId is available and not empty
    if (!sessionId || sessionId.trim() === '') {
      console.warn('⚠️ Session ID not ready, delaying WebSocket connection');
      return;
    }
    
    console.log(`🔌 Initializing voice WebSocket with session: ${sessionId}`);
    connectWebSocket();
    
    return () => {
      if (wsRef.current) {
        // Only send close if WebSocket is open
        if (wsRef.current.readyState === WebSocket.OPEN) {
          try {
            wsRef.current.send(JSON.stringify({ type: 'close' }));
          } catch (err) {
            console.warn('Failed to send close message:', err);
          }
        }
        wsRef.current.close();
      }
      stopAudio();
    };
  }, [sessionId, contextPage]);

  // Update context when page changes
  useEffect(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'update_context',
        context_page: contextPage
      }));
    }
  }, [contextPage]);

  // Start recording
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      // Create audio context for potential visualizations
      audioContextRef.current = new AudioContext();
      
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus'
      });
      
      audioChunksRef.current = [];
      
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };
      
      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        
        // Convert to base64
        const reader = new FileReader();
        reader.onloadend = () => {
          const base64Audio = reader.result as string;
          
          // Send to WebSocket
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            setIsProcessing(true);
            wsRef.current.send(JSON.stringify({
              type: 'audio',
              data: base64Audio,
              format: 'webm'
            }));
          }
        };
        reader.readAsDataURL(audioBlob);
        
        // Stop all tracks
        stream.getTracks().forEach(track => track.stop());
      };
      
      mediaRecorder.start();
      mediaRecorderRef.current = mediaRecorder;
      setIsRecording(true);
      
      console.log('🎤 Recording started');
    } catch (error) {
      console.error('❌ Failed to start recording:', error);
      onError?.('Microphone access denied');
    }
  };

  // Stop recording
  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      console.log('🛑 Recording stopped');
    }
  };

  // Play audio response
  const playAudio = (base64Audio: string) => {
    // Stop any currently playing audio
    stopAudio();
    
    const audio = new Audio(`data:audio/mp3;base64,${base64Audio}`);
    currentAudioRef.current = audio;
    
    audio.onplay = () => {
      setIsSpeaking(true);
      console.log('🔊 Playing audio');
    };
    
    audio.onended = () => {
      setIsSpeaking(false);
      console.log('✅ Audio playback finished');
    };
    
    audio.onerror = (error) => {
      console.error('❌ Audio playback error:', error);
      setIsSpeaking(false);
      onError?.('Failed to play audio response');
    };
    
    audio.play().catch(error => {
      console.error('❌ Failed to play audio:', error);
      setIsSpeaking(false);
    });
  };

  // Stop audio playback
  const stopAudio = () => {
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current.currentTime = 0;
      currentAudioRef.current = null;
      setIsSpeaking(false);
    }
  };

  // Send confirmation response
  const sendConfirmation = async (confirmed: boolean) => {
    const confirmMessage = confirmed ? 'yes' : 'no';
    
    // Add user message
    setMessages(prev => [...prev, {
      type: 'user',
      text: confirmMessage,
      timestamp: new Date()
    }]);
    
    setRequiresConfirmation(false);
    setConsequenceInfo(null);
    
    // Convert text to audio and send
    // For simplicity, we'll use the text chat endpoint for confirmation
    // Alternatively, we could synthesize the word "yes"/"no" locally
    
    // Create a simple audio message (we could use Web Speech API here)
    // For now, send as text through the same pipeline
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      // We'll create a synthetic transcription event
      setIsProcessing(true);
      
      // Send the confirmation text directly as if it was transcribed
      // The backend will process it through the same graph
      try {
        const response = await fetch(`${API_URL}/movi/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: confirmMessage,
            session_id: sessionId,
            context_page: contextPage
          })
        });
        
        const data = await response.json();
        
        // Convert response to speech
        const ttsResponse = await fetch(`${API_URL}/movi/voice/tts`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text: data.response
          })
        });
        
        const audioData = await ttsResponse.json();
        
        setMessages(prev => [...prev, {
          type: 'assistant',
          text: data.response,
          timestamp: new Date(),
          audio: audioData.audio_base64
        }]);
        
        playAudio(audioData.audio_base64);
        setIsProcessing(false);
      } catch (error) {
        console.error('Error sending confirmation:', error);
        setIsProcessing(false);
        onError?.('Failed to send confirmation');
      }
    }
  };

  return {
    isRecording,
    isProcessing,
    isSpeaking,
    messages,
    requiresConfirmation,
    consequenceInfo,
    startRecording,
    stopRecording,
    sendConfirmation,
    stopAudio
  };
}
