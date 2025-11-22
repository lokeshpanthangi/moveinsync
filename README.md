# MoveInSync Fleet Management System

A modern fleet management system with AI-powered voice assistant for managing buses, routes, trips, and drivers.

![System Architecture](image.png)

## 🔗 Live Demo

**[Deploy Link](http://13.234.202.243:8080/auth/login)**

http://13.234.202.243:8080

---

## Architecture

### Backend
- **Framework**: FastAPI (Python)
- **Database**: SQLAlchemy ORM with SQLite/PostgreSQL
- **AI Agent**: LangGraph + OpenAI (GPT-4o/GPT-4o-mini)
- **Features**:
  - RESTful APIs for fleet operations
  - LangGraph-based AI agent with human-in-the-loop
  - Vision support for image analysis
  - Tool calling for database operations

### Frontend
- **Framework**: React + TypeScript + Vite
- **UI**: shadcn/ui + Tailwind CSS
- **Maps**: Mapbox (tiles) + OSRM (routing)
- **Features**:
  - Real-time AI chat assistant
  - Voice chat integration
  - Interactive route maps
  - Responsive dashboard

---

## Setup & Installation

### Prerequisites
- Python 3.10+
- Node.js 18+
- OpenAI API Key
- Mapbox API Token (for maps)

### 1. Clone the Project

```bash
git clone https://github.com/lokeshpanthangi/moveinsync.git
cd moveinsync
```

### 2. Backend Setup

```bash
# Navigate to backend folder
cd backend

# Create .env file and add your OpenAI API key
echo OPENAI_API_KEY=your_openai_key_here > .env

# Install dependencies
pip install -r requirements.txt

# Run backend on port 8000
uvicorn main:app --reload --port 8000
```

Backend will run at: `http://localhost:8000`

### 3. Frontend Setup

```bash
# Navigate to frontend folder (open new terminal)
cd frontend

# Create .env file and add required variables
echo VITE_API_URL=http://localhost:8000 > .env
echo VITE_MAPBOX_ACCESS_TOKEN=your_mapbox_token_here >> .env

# Install dependencies
npm install

# Run frontend
npm run dev
```

Frontend will run at: `http://localhost:8080`

---

## How It Works

### AI Agent Flow (LangGraph)

The system uses a **5-node LangGraph architecture** with human-in-the-loop for safe operations:

#### 1. **Intent Node**
- Receives user input (text or image)
- Uses GPT-4o for vision analysis if image is present
- Classifies user intent and extracts entities
- Selects appropriate tool from 24+ available tools
- **Output**: `tool_name`, `entities`, `intent`

#### 2. **Consequence Node**
- Checks if selected tool is high-impact (deletions, updates)
- Fetches real database consequences for the action
- **Triggers interrupt** for human approval using `interrupt()`
- **Output**: Pauses execution, waits for user confirmation

#### 3. **Tool Call Node**
- Executes the approved tool with extracted entities
- Performs database operations (CRUD)
- Handles errors and validation
- **Output**: `tool_result` with success/error message

#### 4. **Response Node**
- Generates natural language response using GPT-4o-mini
- Explains what happened in user-friendly terms
- Provides relevant follow-up suggestions
- **Output**: Final AI message to user

#### 5. **END**
- Returns response to frontend
- State saved for conversation continuity

### Tool Categories

**Bus Dashboard Tools** (12 tools)
- Trip management: create, update, delete trips
- Vehicle assignment and removal
- Deployment management
- Trip analytics and listing

**Stops & Paths Tools** (7 tools)
- Stop creation and management
- Path configuration with ordered stops
- Geographic data handling

**Routes Tools** (5 tools)
- Route creation and updates
- Status management (active/deactivated)
- Capacity and scheduling

### Human-in-the-Loop (HITL)

High-impact actions trigger AI-generated confirmation alerts:
- **Delete operations**: Trips, vehicles, routes, drivers
- **Update operations**: Critical fields like status, assignments
- AI analyzes consequences and generates contextual warnings
- User approves/rejects via natural language ("yes"/"no")

### Vision Support

- Upload screenshots of dashboards
- AI identifies highlighted/circled items (GPT-4o)
- Extracts trip names, statuses, booking percentages
- Uses visual emphasis to understand user intent

---

## Key Features

- 🤖 **AI Assistant (Movi)**: Natural language interface for fleet management
- 🗣️ **Voice Chat**: Hands-free operation support
- 🗺️ **Route Visualization**: Interactive maps with OSRM routing
- 📊 **Analytics Dashboard**: Real-time fleet metrics
- ✅ **Human-in-the-Loop**: AI confirms high-impact actions
- 🎨 **Modern UI**: Clean, responsive interface with green theme

---

## Project Structure

```
moveinsync/
├── backend/
│   ├── Agents/          # LangGraph AI agent
│   ├── crud/            # Database operations
│   ├── routes/          # API endpoints
│   ├── models.py        # Database models
│   └── main.py          # FastAPI app
│
└── frontend/
    ├── src/
    │   ├── components/  # React components
    │   ├── pages/       # Page components
    │   └── hooks/       # Custom hooks
    └── package.json
```

---

## Author

**Lokesh Panthangi**

- GitHub: [@lokeshpanthangi](https://github.com/lokeshpanthangi)
- Repository: [moveinsync](https://github.com/lokeshpanthangi/moveinsync.git)

---

## License

MIT

