# Booking Agent Directive

## Goal
To manage appointment bookings, check availability, and maintain conversation context for a user.

## Tools
All logic is exposed via the API at `http://localhost:8000`.

### 1. Calendar Operations
- **List Events**: `GET /calendar/events`
    - Input: `limit` (optional, default 10)
    - Output: List of event objects (summary, start, end).
- **Book Event**: `POST /calendar/book`
    - Input: JSON `{ "summary": "...", "start_time": "ISO...", "end_time": "ISO...", "description": "..." }`
    - Output: Created event details.
- **Cancel Event**: `POST /calendar/cancel`
    - Input: JSON `{ "event_id": "..." }`

### 2. History Operations
- **Add Message**: `POST /history/add`
    - Input: JSON `{ "user_id": "...", "role": "user"|"assistant", "content": "..." }`
- **Get History**: `GET /history/list`
    - Input: `user_id`, `limit` (default 10)
    - Output: List of messages in chronological order.

## Workflow (for n8n)

1. **Receive Message**: n8n triggers on chat input.
2. **Context Retrieval**: 
    - Call `GET /history/list` to get previous context.
    - Append current user message to this list for the prompt.
3. **Save User Message**:
    - Call `POST /history/add` with user's message.
4. **LLM Decision**:
    - Send context + user message to LLM (OpenAI/Anthropic node in n8n).
    - Instruct LLM to output a JSON or specific function call if it needs to book/list.
5. **Tool Execution (Switch)**:
    - If LLM says "BOOK": Call `POST /calendar/book`.
    - If LLM says "LIST": Call `GET /calendar/events`.
6. **Generate Response**:
    - Use tool output to generate final natural language response.
7. **Save Agent Response**:
    - Call `POST /history/add` with assistant's response.
8. **Reply**: Send text back to user in n8n.
