# Backend Service

## Overview
This is the backend service for the application, providing core functionality including BPM flows, user management, and business logic.

## Documentation

### Core Documentation
- [API Documentation](docs/API.md) - API endpoints and usage
- [Database Schema](docs/DATABASE_SCHEMA.md) - Database structure and relationships
- [Authentication](docs/AUTHENTICATION.md) - Authentication and authorization system

### BPM System
- [BPM Flow Enhancements](docs/BPM_ENHANCEMENTS.md) - Advanced BPM features and enhancements
- [BPM Async Migration](docs/BPM_ASYNC_MIGRATION.md) - Strategy for migrating to asynchronous architecture
- [Dynamic Forms](docs/DYNAMIC_FORMS.md) - Implementation of dynamic forms in React

### Development Guides
- [Setup Guide](docs/SETUP.md) - Local development setup instructions
- [Testing Guide](docs/TESTING.md) - Testing procedures and guidelines
- [Deployment Guide](docs/DEPLOYMENT.md) - Deployment procedures and configurations

## Project Structure
```
backend/
├── src/
│   ├── app/              # Main application code
│   ├── core/             # Core functionality
│   ├── bpm/              # BPM system (async implementation)
│   └── tests/            # Test suite
├── docs/                 # Documentation
└── scripts/              # Utility scripts
```

## Getting Started

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Run the development server:
```bash
uvicorn app.main:app --reload
```

## Contributing
Please read our [Contributing Guidelines](docs/CONTRIBUTING.md) before submitting pull requests.

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
