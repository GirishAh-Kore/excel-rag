# Excel RAG System - Frontend

A React-based web application for querying Excel files using natural language, built with TypeScript, Material-UI, and Vite.

## Features

### Authentication
- Login page with username/password authentication
- JWT token-based authentication
- Protected routes for authenticated users
- Automatic token refresh and error handling

### Configuration Page
- **Google Drive Integration**: Connect/disconnect Google Drive account
- **File Upload**: Drag-and-drop or browse to upload Excel files (.xlsx, .xls, .xlsm)
- **Indexed Files Management**: View, search, filter, reindex, and delete indexed files
- Tabbed interface for easy navigation

### Chat Interface
- Natural language query input with multi-line support
- Real-time message display with user and assistant messages
- Source citations with expandable details (file name, sheet name, cell range)
- Confidence scores displayed as badges
- Conversation history sidebar
- Create new conversations and delete old ones
- Session management for follow-up questions

### Responsive Design
- Mobile-first design with breakpoints for tablet and desktop
- Adaptive layouts that work on all screen sizes
- Touch-friendly interface for mobile devices
- Accessible components with ARIA labels and keyboard navigation

## Technology Stack

- **React 19** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **Material-UI (MUI)** - Component library
- **React Router** - Client-side routing
- **Axios** - HTTP client with interceptors and retry logic

## Project Structure

```
frontend/
├── src/
│   ├── components/        # Reusable UI components
│   │   ├── ChatInterface.tsx
│   │   ├── ConversationSidebar.tsx
│   │   ├── FileUpload.tsx
│   │   ├── GDriveConnection.tsx
│   │   ├── IndexedFilesList.tsx
│   │   ├── LoadingSkeleton.tsx
│   │   ├── LoginForm.tsx
│   │   ├── MessageItem.tsx
│   │   ├── MessageList.tsx
│   │   ├── ProtectedRoute.tsx
│   │   └── QueryInput.tsx
│   ├── pages/             # Page components
│   │   ├── ChatPage.tsx
│   │   ├── ConfigPage.tsx
│   │   └── LoginPage.tsx
│   ├── services/          # API services
│   │   ├── api.ts         # Axios client with interceptors
│   │   ├── authService.ts
│   │   ├── chatService.ts
│   │   └── fileService.ts
│   ├── hooks/             # Custom React hooks
│   │   ├── useAuth.ts
│   │   └── useLoading.ts
│   ├── types/             # TypeScript type definitions
│   │   └── index.ts
│   ├── utils/             # Utility functions
│   │   └── toast.ts
│   ├── App.tsx            # Main app component with routing
│   ├── main.tsx           # App entry point
│   └── index.css          # Global styles
├── public/                # Static assets
├── .env.example           # Environment variables template
├── package.json
├── tsconfig.json
├── vite.config.ts
└── README.md
```

## Getting Started

### Prerequisites

- Node.js 20.19+ or 22.12+
- npm or yarn

### Installation

1. Install dependencies:
```bash
npm install
```

2. Create environment file:
```bash
cp .env.example .env
```

3. Update `.env` with your API base URL:
```
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

### Development

Start the development server:
```bash
npm run dev
```

The app will be available at `http://localhost:5173`

### Build

Build for production:
```bash
npm run build
```

The built files will be in the `dist/` directory.

### Preview Production Build

Preview the production build locally:
```bash
npm run preview
```

## API Integration

The frontend communicates with the backend API through the following services:

### Authentication Service
- `POST /auth/login` - Login with credentials
- `POST /auth/logout` - Logout and revoke tokens
- `GET /auth/status` - Check authentication status

### File Service
- `POST /files/upload` - Upload Excel files
- `GET /files/list` - List indexed files with pagination
- `DELETE /files/{file_id}` - Delete a file
- `POST /files/{file_id}/reindex` - Reindex a file
- `GET /files/indexing-status` - Get indexing status
- `GET /config/gdrive/status` - Get Google Drive connection status
- `POST /config/gdrive/connect` - Connect to Google Drive
- `DELETE /config/gdrive/disconnect` - Disconnect from Google Drive

### Chat Service
- `POST /query` - Submit a natural language query
- `GET /chat/sessions` - List chat sessions
- `POST /chat/sessions` - Create a new session
- `DELETE /chat/sessions/{session_id}` - Delete a session
- `GET /chat/sessions/{session_id}/history` - Get session history
- `POST /query/feedback` - Submit feedback on query results

## Features in Detail

### Error Handling
- Automatic retry logic for failed requests (3 retries with exponential backoff)
- 401 errors automatically redirect to login
- User-friendly error messages
- Correlation IDs for debugging

### Loading States
- Loading spinners during API calls
- Skeleton screens for better UX
- Progress bars for file uploads
- Disabled states during processing

### Accessibility
- ARIA labels on interactive elements
- Keyboard navigation support
- Focus visible indicators
- Semantic HTML structure
- Screen reader friendly

### Responsive Design
- Mobile: Single column layout, hidden sidebar
- Tablet: Optimized spacing and font sizes
- Desktop: Full sidebar and multi-column layouts
- Breakpoints: xs (0px), sm (600px), md (960px), lg (1280px), xl (1920px)

## Environment Variables

Create a `.env` file based on `.env.example`:

```bash
# API Configuration
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## Contributing

When adding new features:

1. Create components in `src/components/`
2. Add types to `src/types/index.ts`
3. Create services in `src/services/`
4. Use Material-UI components for consistency
5. Follow the existing code style
6. Ensure responsive design
7. Add accessibility attributes

## License

This project is part of the Excel RAG System.
