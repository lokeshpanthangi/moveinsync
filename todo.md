# 🤖 Movi AI Assistant - Implementation Roadmap

## 📋 Project Overview
Building "Movi" - A multimodal AI assistant using LangGraph for the MoveInSync bus management system.

**Target Pages**: Routes, Bus Dashboard, Stops & Paths  
**Core Tech**: LangGraph, LangChain, OpenAI (GPT-4, Whisper, TTS, Vision)

---

## 🎯 Core Requirements

### ✅ Must Have Features
- [ ] Voice Input (Speech-to-Text using Whisper)
- [ ] Voice Output (Text-to-Speech)
- [ ] Text Chat Interface
- [ ] Image Understanding (Vision for screenshots)
- [ ] 10+ Distinct Actions (Read, Create, Update, Delete)
- [ ] Tribal Knowledge (Consequence checking with confirmation flow)
- [ ] Stateful Conversation (LangGraph state persistence)
- [ ] Multimodal Input Processing

---

## 📦 Phase 1: Foundation Setup (Days 1-2)

### Backend Setup
- [x] Install Python dependencies
  - [x] `langgraph`
  - [x] `langchain`
  - [x] `langchain-openai`
  - [x] `openai`
  - [x] `python-multipart` (for file uploads)
  
- [x] Create directory structure
  - [x] `backend/agents/` - Main agent code
  - [x] `backend/agents/nodes/` - LangGraph nodes
  - [x] `backend/agents/tools/` - Action tools
  - [x] `backend/agents/state.py` - State schema
  - [x] `backend/agents/graph.py` - LangGraph definition
  
- [x] Create Movi state schema
  - [x] Define `MoviState` TypedDict
  - [x] Add fields: messages, user_intent, action_type, target_entity, parameters
  - [x] Add fields: consequences, requires_confirmation, confirmed
  - [x] Add fields: current_page, image_context, audio_input

- [x] Build basic LangGraph structure
  - [x] Create graph builder
  - [x] Add START and END nodes
  - [x] Create simple linear flow (parse → intent → execute → response)
  - [x] Test graph compilation

- [x] Create FastAPI Movi endpoints
  - [x] POST `/api/movi/chat` - Text chat
  - [ ] POST `/api/movi/voice` - Voice input (Phase 4)
  - [ ] POST `/api/movi/image` - Image upload (Phase 4)
  - [ ] GET `/api/movi/audio/{message_id}` - Audio output (Phase 4)
  - [x] Add CORS configuration (already in main.py)

### Frontend Setup
- [x] Create Movi components directory
  - [x] `frontend/src/components/movi/`
  
- [x] Build basic chat UI
  - [x] `MoviChat.tsx` - Main chat container
  - [x] `MoviMessage.tsx` - Individual message component (integrated in MoviChat)
  - [x] `MoviInput.tsx` - Text input with send button (integrated in MoviChat)
  - [x] `MoviFloatingButton.tsx` - Floating chat trigger button
  
- [x] Create chat hook
  - [x] `useMoviChat.ts` - API communication (integrated directly in MoviChat)
  - [x] Handle message sending
  - [x] Handle message receiving
  - [x] Handle loading states

- [x] Add Movi to 3 target pages
  - [x] Integrate into Bus Dashboard
  - [ ] Integrate into Routes page
  - [ ] Integrate into Stops & Paths page

---

## 🛠️ Phase 2: Core Tools Implementation (Days 3-4)

### Bus Dashboard Tools (4 Actions)
- [x] **Read Tool 1**: Get unassigned vehicles count
  - [x] Create `get_unassigned_vehicles` tool
  - [x] Query vehicles not in deployments table
  - [x] Return count and list
  
- [x] **Read Tool 2**: Get trip status
  - [x] Create `get_trip_status` tool
  - [x] Accept trip name/ID
  - [x] Return status, booking %, deployments
  
- [x] **Create Tool 3**: Assign vehicle and driver to trip
  - [x] Create `assign_vehicle_to_trip` tool
  - [x] Validate vehicle/driver/trip exist
  - [x] Check availability
  - [x] Create deployment record
  
- [x] **Delete Tool 4**: Remove vehicle from trip
  - [x] Create `remove_vehicle_from_trip` tool
  - [x] Find deployment by trip
  - [x] Delete deployment record

### Routes Tools (3 Actions)
- [ ] **Read Tool 5**: Get routes using specific path
  - [ ] Create `get_routes_by_path` tool
  - [ ] Query routes with path_id
  - [ ] Return route details
  
- [ ] **Create Tool 6**: Create new route
  - [ ] Create `create_route` tool
  - [ ] Accept route parameters (name, path, shift, direction)
  - [ ] Validate path exists
  - [ ] Insert route record
  
- [ ] **Update Tool 7**: Update route shift time
  - [ ] Create `update_route_shift_time` tool
  - [ ] Find route by name/ID
  - [ ] Update shift_time field

### Stops & Paths Tools (5 Actions)
- [ ] **Read Tool 8**: List stops for a path
  - [ ] Create `get_stops_for_path` tool
  - [ ] Query path by name/ID
  - [ ] Get ordered stops list
  - [ ] Return stop details
  
- [ ] **Create Tool 9**: Create new stop
  - [ ] Create `create_stop` tool
  - [ ] Accept name, lat, lon
  - [ ] Insert stop record
  
- [ ] **Create Tool 10**: Create new path with stops
  - [ ] Create `create_path_with_stops` tool
  - [ ] Accept path name and stop names list
  - [ ] Resolve stop IDs
  - [ ] Create path record
  - [ ] Create ordered stop associations
  
- [ ] **Delete Tool 11**: Delete stop
  - [ ] Create `delete_stop` tool
  - [ ] Find stop by name/ID
  - [ ] Delete stop record
  
- [ ] **Update Tool 12**: Reorder stops in path
  - [ ] Create `reorder_path_stops` tool
  - [ ] Update stop_order values
  - [ ] Maintain path integrity

### Intent Extraction Node
- [ ] Create `extract_intent.py` node
  - [ ] Use LLM to classify user intent
  - [ ] Identify action_type (read, create, update, delete)
  - [ ] Identify target_entity (vehicle, trip, route, stop, path)
  - [ ] Extract parameters from natural language
  - [ ] Update state with structured intent

### Tool Executor Node
- [ ] Create `execute_action.py` node
  - [ ] Map intent to appropriate tool
  - [ ] Execute tool with parameters
  - [ ] Handle tool errors
  - [ ] Update state with results

---

## 🧠 Phase 3: Tribal Knowledge (Consequence System) (Days 5-6)

### Consequence Checker Node
- [ ] Create `check_consequences.py` node
  - [ ] Implement consequence rules engine
  - [ ] Check for impactful actions
  
- [ ] **Consequence Rule 1**: Vehicle removal from booked trip
  - [ ] Check trip.booking_status_percentage > 0
  - [ ] Check trip.live_status == "scheduled"
  - [ ] Generate warning message
  - [ ] Set requires_confirmation = True
  
- [ ] **Consequence Rule 2**: Stop deletion with path dependencies
  - [ ] Query paths using this stop
  - [ ] Count affected paths and routes
  - [ ] Generate warning message
  - [ ] Set requires_confirmation = True
  
- [ ] **Consequence Rule 3**: Vehicle already deployed
  - [ ] Check existing deployments for vehicle
  - [ ] Identify conflicting trip
  - [ ] Generate warning message
  - [ ] Set requires_confirmation = True
  
- [ ] **Consequence Rule 4**: Path deletion with route dependencies
  - [ ] Query routes using this path
  - [ ] Count affected routes
  - [ ] Generate warning message
  - [ ] Set requires_confirmation = True

### Confirmation Flow Node
- [ ] Create `get_confirmation.py` node
  - [ ] Format consequence warnings
  - [ ] Add "Do you want to proceed?" prompt
  - [ ] Set state to await user response
  - [ ] Return confirmation request

- [ ] Create `await_confirmation.py` node
  - [ ] Parse user response (yes/no)
  - [ ] Update state.confirmed flag
  - [ ] Route to execute or cancel

### Conditional Routing
- [ ] Add conditional edges in graph
  - [ ] After check_consequences: route to confirmation OR execute
  - [ ] After get_confirmation: route to execute OR cancel
  - [ ] Handle cancellation gracefully

---

## 🎙️ Phase 4: Multimodal Integration (Days 7-8)

### Speech-to-Text (Voice Input)
- [ ] Create `audio_tools.py`
  - [ ] Implement Whisper STT
  - [ ] Create `transcribe_audio` function
  - [ ] Handle audio formats (webm, mp3, wav)
  - [ ] Add error handling

- [ ] Create voice input node
  - [ ] Add to `parse_input.py`
  - [ ] Detect audio input in state
  - [ ] Call transcription tool
  - [ ] Update state with text

- [ ] Frontend voice recording
  - [ ] Create `MoviVoiceInput.tsx`
  - [ ] Implement Web Audio API recording
  - [ ] Add record/stop buttons
  - [ ] Show recording indicator
  - [ ] Send audio to backend

### Text-to-Speech (Voice Output)
- [ ] Create TTS in `audio_tools.py`
  - [ ] Implement OpenAI TTS
  - [ ] Create `text_to_speech` function
  - [ ] Return audio bytes
  - [ ] Cache audio files

- [ ] Add TTS to response node
  - [ ] Generate speech for each response
  - [ ] Store audio file path in state
  - [ ] Return audio URL to frontend

- [ ] Frontend audio playback
  - [ ] Add audio player to `MoviMessage.tsx`
  - [ ] Auto-play option toggle
  - [ ] Show speaker icon
  - [ ] Handle playback errors

### Vision (Image Understanding)
- [ ] Create `vision_tools.py`
  - [ ] Implement GPT-4V integration
  - [ ] Create `analyze_screenshot` function
  - [ ] Extract trip names, vehicle IDs, stop names
  - [ ] Return structured data

- [ ] Create image input node
  - [ ] Add to `parse_input.py`
  - [ ] Detect image in state
  - [ ] Call vision tool with user query
  - [ ] Merge image context with intent

- [ ] Frontend image upload
  - [ ] Create `MoviImageUpload.tsx`
  - [ ] Drag-and-drop support
  - [ ] Screenshot paste support
  - [ ] Image preview
  - [ ] Send base64 to backend

---

## 🎨 Phase 5: UI/UX Polish (Days 9-10)

### Chat UI Enhancements
- [ ] Add typing indicators
- [ ] Add message timestamps
- [ ] Add user avatars
- [ ] Add Movi avatar/icon
- [ ] Smooth scroll to bottom
- [ ] Message grouping by time

### Confirmation UI
- [ ] Create confirmation dialog component
- [ ] Show consequence warnings prominently
- [ ] Add Yes/No/Cancel buttons
- [ ] Highlight affected entities

### Error Handling
- [ ] Backend error messages
  - [ ] Tool execution errors
  - [ ] LLM API errors
  - [ ] Database errors
  
- [ ] Frontend error display
  - [ ] Show error messages in chat
  - [ ] Retry mechanism
  - [ ] Fallback to text if voice fails

### Loading States
- [ ] Show "Movi is thinking..." indicator
- [ ] Show "Transcribing audio..." for voice
- [ ] Show "Analyzing image..." for vision
- [ ] Show "Checking consequences..." during validation

### Accessibility
- [ ] Keyboard navigation
- [ ] Screen reader support
- [ ] Focus management
- [ ] ARIA labels

---

## 🧪 Phase 6: Testing & Optimization (Day 11)

### Testing
- [ ] Test all 12 tools independently
- [ ] Test consequence checking scenarios
- [ ] Test voice input/output
- [ ] Test image understanding
- [ ] Test error cases
- [ ] Test on all 3 pages

### Performance Optimization
- [ ] Cache LLM responses
- [ ] Optimize database queries
- [ ] Compress audio files
- [ ] Lazy load chat UI

### Documentation
- [ ] Document API endpoints
- [ ] Document tool schemas
- [ ] Create user guide for Movi
- [ ] Add code comments

---

## 📊 Success Criteria

### Functional Requirements
- [x] Text chat works across all 3 pages
- [ ] Voice input transcription accurate
- [ ] Voice output plays correctly
- [ ] Image understanding identifies entities
- [ ] All 12 tools execute successfully
- [ ] Consequence checking triggers appropriately
- [ ] Confirmation flow works end-to-end

### Technical Requirements
- [ ] LangGraph state persists correctly
- [ ] Conditional routing works
- [ ] Error handling comprehensive
- [ ] API response time < 3s (text)
- [ ] API response time < 10s (voice/vision)

### User Experience
- [ ] Chat UI intuitive
- [ ] Movi responses clear and helpful
- [ ] Consequence warnings understandable
- [ ] Multimodal inputs seamless

---

## 🚀 Current Status

**Phase**: Phase 1-2 Implementation Complete (TESTING NEEDED) ⚠️  
**Last Updated**: November 13, 2025  
**Next Action**: TEST backend startup and API endpoints before frontend integration

### ⚠️ Status: Code Written, Not Yet Tested

**What's Built:**
- ✅ LangGraph agent structure (4 nodes)
- ✅ 4 Bus Dashboard tools
- ✅ Intent extraction with GPT-4
- ✅ Response formatting with GPT-4
- ✅ FastAPI `/api/movi/chat` endpoint
- ✅ MoviChat UI component
- ✅ Integration in Bus Dashboard page

**What Needs Testing:**
1. ❓ Backend starts without errors
2. ❓ Movi API endpoints work
3. ❓ LangGraph executes properly
4. ❓ Tools query database successfully
5. ❓ Frontend connects to backend
6. ❓ End-to-end chat flow works

### 🧪 Immediate Next Steps:

**Step 1:** Test backend startup
```bash
cd backend
uvicorn main:app --reload
```

**Step 2:** Test health endpoint
```bash
curl http://localhost:8000/api/movi/health
```

**Step 3:** Test chat with simple query
```bash
curl -X POST http://localhost:8000/api/movi/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "How many vehicles are not assigned?", "current_page": "busDashboard"}'
```

**Step 4:** Fix any errors found

**Step 5:** Test frontend integration

See `MOVI_STATUS.md` for detailed testing checklist and known issues.

---

## 📝 Notes & Decisions

### Technology Choices
- **LLM**: OpenAI GPT-4 (for reliability)
- **STT**: OpenAI Whisper
- **TTS**: OpenAI TTS (Nova voice)
- **Vision**: GPT-4V
- **State Persistence**: In-memory (can add Redis later)

### Open Questions
- [ ] Should conversation history persist across sessions?
- [ ] Rate limiting strategy?
- [ ] Audio format preference?
- [ ] WebSocket vs REST for real-time chat?

---

## 🎯 Quick Start Commands

```bash
# Backend - Install dependencies
cd backend
pip install langgraph langchain langchain-openai openai python-multipart

# Frontend - No new dependencies needed (use existing fetch API)

# Start development
# Terminal 1: Backend
cd backend
uvicorn main:app --reload

# Terminal 2: Frontend
cd frontend
npm run dev
```
