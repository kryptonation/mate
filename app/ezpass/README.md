# EZPass Module - Theoretical Architecture & Implementation Documentation

## Table of Contents
1. [Business Context & Purpose](#business-context--purpose)
2. [Architectural Design](#architectural-design)
3. [Layer-by-Layer Design](#layer-by-layer-design)
4. [Data Flow & Processing](#data-flow--processing)
5. [Business Logic Implementation](#business-logic-implementation)
6. [Design Patterns Used](#design-patterns-used)
7. [Integration Architecture](#integration-architecture)
8. [Error Handling Strategy](#error-handling-strategy)

---

## 1. Business Context & Purpose

### What is EZPass?

**EZPass** is an electronic toll collection system used across multiple states in the United States. For the Big Apple Taxi Management System (BATM), the EZPass module manages toll transactions that taxi vehicles incur while operating.

### Business Problem

Taxi companies need to:
1. **Track toll expenses** for each vehicle/driver
2. **Associate tolls** with the correct driver who was operating the vehicle
3. **Bill drivers** for tolls they incurred during their shift
4. **Maintain accurate financial records** in the ledger system
5. **Reconcile** toll charges with lease agreements

### Business Workflow

```
Driver operates taxi → Vehicle passes through toll → EZPass records transaction
→ Company receives toll report → Import to BATM → Match to active lease
→ Identify responsible driver → Post charge to driver's account
→ Driver pays as part of lease obligations
```

### Key Business Rules

1. **Attribution**: Tolls must be attributed to whoever was leasing the vehicle at the time
2. **Time-Based Association**: Match toll timestamp to active lease period
3. **Financial Responsibility**: Driver in lease pays the toll (not vehicle owner)
4. **Accounting**: Tolls are debits (charges) to driver accounts

---

## 2. Architectural Design

### Overall Architecture Pattern

The EZPass module follows a **modern layered architecture** with **dependency injection** and **async operations**:

```
┌─────────────────────────────────────────────┐
│         Presentation Layer (Router)          │  ← HTTP Endpoints
├─────────────────────────────────────────────┤
│         Business Logic Layer (Service)       │  ← Business Rules
├─────────────────────────────────────────────┤
│      Data Access Layer (Repository)          │  ← Database Operations
├─────────────────────────────────────────────┤
│         Domain Layer (Models)                │  ← Data Structures
└─────────────────────────────────────────────┘
```

### Why This Architecture?

**Separation of Concerns**:
- Each layer has a single, well-defined responsibility
- Changes in one layer don't require changes in others
- Easy to test each layer independently

**Dependency Inversion**:
- Higher layers depend on abstractions, not concrete implementations
- Services don't know about HTTP or database details
- Repositories don't know about business rules

**Async-First Design**:
- Non-blocking I/O operations
- Can handle thousands of concurrent requests
- Efficient resource utilization
- Better scalability

---

## 3. Layer-by-Layer Design

### Layer 1: Domain Layer (Models)

**Purpose**: Define the structure of business entities

**Theoretical Concepts**:

1. **Entity Modeling**
   - `EZPassTransaction`: Represents a single toll transaction
   - `EZPassLog`: Represents an import/processing operation

2. **Data Integrity**
   - Primary keys ensure uniqueness
   - Foreign keys maintain relationships
   - Indexes optimize query performance
   - Constraints enforce business rules

3. **Audit Trail**
   - Every record tracks who created/modified it
   - Timestamps track when changes occurred
   - Supports compliance and debugging

**Key Design Decisions**:

- **SQLAlchemy 2.x Mapped Types**: Type safety at compile time
- **Relationships**: ORM handles joins automatically
- **MySQL Optimization**: Proper indexing for large datasets

### Layer 2: Data Access Layer (Repository)

**Purpose**: Abstract all database operations

**Theoretical Concepts**:

1. **Repository Pattern**
   ```
   Client → Repository Interface → Actual Implementation → Database
   ```
   - Provides collection-like interface to domain objects
   - Hides database complexity from business logic
   - Enables easy switching of data sources

2. **Query Building**
   - **Dynamic Filtering**: Build queries based on provided criteria
   - **Pagination**: Efficiently handle large result sets
   - **Sorting**: Allow flexible ordering of results

3. **Transaction Management**
   - Repository operations within a session
   - Automatic rollback on errors
   - Flush vs Commit strategies

**Design Principles**:

- **Single Responsibility**: Repository only does data access
- **Abstraction**: Business logic never writes SQL
- **Testability**: Can mock repository in tests

### Layer 3: Business Logic Layer (Service)

**Purpose**: Implement all business rules and workflows

**Theoretical Concepts**:

1. **Service Layer Pattern**
   - Orchestrates multiple repository operations
   - Implements business logic
   - Manages transactions across multiple operations
   - Provides high-level operations to presentation layer

2. **Business Operations**:

   **Import Operation**:
   ```
   Receive file → Validate format → Parse data → Transform to domain objects
   → Bulk insert → Create audit log → Return statistics
   ```

   **Association Operation**:
   ```
   Get unassociated transactions → For each transaction:
     - Find vehicle by plate number
     - Find active lease for vehicle on transaction date
     - Get driver from lease
     - Get medallion from lease
     - Update transaction with associations
   → Create audit log → Return statistics
   ```

   **Posting Operation**:
   ```
   Get associated transactions → For each transaction:
     - Verify lease still exists
     - Create ledger entry (Debit type)
     - Update transaction as posted
     - Set posting date
   → Create audit log → Return statistics
   ```

3. **Business Rule Enforcement**:
   - **Active Lease Check**: Lease must be active on transaction date
   - **Date Range Validation**: Transaction date must fall within lease period
   - **Primary Driver Selection**: Use primary driver or first driver in lease
   - **Amount Calculation**: Transaction amount becomes ledger debit

**Design Patterns Used**:

- **Strategy Pattern**: Different association strategies per business rules
- **Template Method**: Common workflow with specific implementations
- **Chain of Responsibility**: Error handling at each step

### Layer 4: Presentation Layer (Router)

**Purpose**: Handle HTTP requests and responses

**Theoretical Concepts**:

1. **RESTful API Design**
   ```
   POST /ezpass/import          → Create (import data)
   GET  /ezpass/transactions     → Read (list with filters)
   GET  /ezpass/transaction/{id} → Read (single item)
   PUT  /ezpass/transaction/{id} → Update
   POST /ezpass/associate        → Process (business operation)
   POST /ezpass/post             → Process (business operation)
   ```

2. **Request Processing Flow**:
   ```
   HTTP Request → Authentication → Validation → Service Call
   → Business Logic → Database Operations → Response Building
   → HTTP Response
   ```

3. **Responsibility Separation**:
   - **Router**: HTTP concerns (request/response, status codes)
   - **Service**: Business logic (what to do)
   - **Repository**: Data access (how to store/retrieve)

---

## 4. Data Flow & Processing

### Import Data Flow

```
┌─────────────┐
│ CSV/Excel   │
│ File Upload │
└──────┬──────┘
       │
       ↓
┌─────────────────┐
│ File Validation │ ← utils.py validates format
├─────────────────┤
│ - Check format  │
│ - Parse columns │
│ - Validate data │
└──────┬──────────┘
       │
       ↓
┌──────────────────┐
│ Data             │ ← services.py processes
│ Transformation   │
├──────────────────┤
│ - Clean data     │
│ - Create objects │
│ - Validate rules │
└──────┬───────────┘
       │
       ↓
┌──────────────────┐
│ Bulk Insert      │ ← repository.py persists
├──────────────────┤
│ - Transaction    │
│ - Commit         │
│ - Create log     │
└──────┬───────────┘
       │
       ↓
┌──────────────────┐
│ Response         │
│ Statistics       │
└──────────────────┘
```

### Association Data Flow

```
┌────────────────────┐
│ Get Unassociated   │
│ Transactions       │
│ (status=Imported)  │
└─────────┬──────────┘
          │
          ↓
    ┌─────────────┐
    │ For Each    │
    │ Transaction │
    └──────┬──────┘
           │
           ↓
┌──────────────────────────────┐
│ Find Vehicle by Plate Number │
│                               │
│ Query: VehicleRegistration    │
│ WHERE plate_no = 'ABC123'     │
└──────────┬───────────────────┘
           │
           ↓ (vehicle found)
┌──────────────────────────────┐
│ Find Active Lease             │
│                               │
│ Query: Lease                  │
│ WHERE vehicle_id = X          │
│   AND start_date <= txn_date  │
│   AND end_date >= txn_date    │
│   AND is_active = true        │
└──────────┬───────────────────┘
           │
           ↓ (lease found)
┌──────────────────────────────┐
│ Get Driver from Lease         │
│                               │
│ Query: LeaseDriver            │
│ WHERE lease_id = Y            │
│   AND is_primary = true       │
└──────────┬───────────────────┘
           │
           ↓ (driver found)
┌──────────────────────────────┐
│ Get Medallion from Lease      │
│                               │
│ Query: Medallion              │
│ WHERE id = lease.medallion_id │
└──────────┬───────────────────┘
           │
           ↓
┌──────────────────────────────┐
│ Update Transaction            │
│                               │
│ SET driver_id = X             │
│     vehicle_id = Y            │
│     medallion_no = 'M123'     │
│     status = 'Associated'     │
└──────────┬───────────────────┘
           │
           ↓
┌──────────────────────────────┐
│ Mark as Associated            │
│ Continue to Next Transaction  │
└───────────────────────────────┘
```

### Posting Data Flow

```
┌────────────────────┐
│ Get Associated     │
│ Transactions       │
│ (status=Associated)│
└─────────┬──────────┘
          │
          ↓
    ┌─────────────┐
    │ For Each    │
    │ Transaction │
    └──────┬──────┘
           │
           ↓
┌──────────────────────────────┐
│ Get Lease Details             │
│                               │
│ Verify: Lease still active    │
│         All associations exist│
└──────────┬───────────────────┘
           │
           ↓ (verified)
┌──────────────────────────────┐
│ Create Ledger Entry           │
│                               │
│ INSERT INTO ledger            │
│ VALUES (                      │
│   transaction_date = txn_date │
│   posting_date = today        │
│   amount = txn_amount         │
│   transaction_type = 'Debit'  │
│   source_type = 'EZPASS'      │
│   source_id = txn_id          │
│   driver_id = X               │
│   vehicle_id = Y              │
│   lease_id = Z                │
│   medallion_id = M            │
│   description = '...'         │
│ )                             │
└──────────┬───────────────────┘
           │
           ↓ (ledger created)
┌──────────────────────────────┐
│ Update Transaction            │
│                               │
│ SET status = 'Posted'         │
│     posting_date = today      │
└──────────┬───────────────────┘
           │
           ↓
┌──────────────────────────────┐
│ Mark as Posted                │
│ Continue to Next Transaction  │
└───────────────────────────────┘
```

---

## 5. Business Logic Implementation

### Association Logic - Detailed Theory

**Problem**: Given a toll transaction with only a plate number and date, identify the responsible driver.

**Solution Strategy**:

1. **Vehicle Identification**
   ```
   Input: Plate number (e.g., "ABC123")
   Process: Search vehicle registration records
   Challenge: Plate numbers may have variations (ABC-123, ABC 123)
   Solution: Normalize plate numbers (remove special chars, uppercase)
   Output: Vehicle ID
   ```

2. **Temporal Lease Matching**
   ```
   Input: Vehicle ID + Transaction Date
   Process: Find lease where transaction date falls within lease period
   Rule: start_date ≤ transaction_date ≤ end_date (or end_date is NULL)
   Additional: Lease must be marked as active
   Challenge: Multiple historical leases may exist for same vehicle
   Solution: Order by start_date DESC, take most recent active lease
   Output: Lease ID
   ```

3. **Driver Identification**
   ```
   Input: Lease ID
   Process: Get drivers associated with lease
   Rule: Prefer primary driver if exists, otherwise use first driver
   Challenge: Lease may have multiple drivers (day/night shift)
   Business Decision: Primary driver is financially responsible
   Output: Driver ID
   ```

4. **Medallion Attribution**
   ```
   Input: Lease ID
   Process: Get medallion associated with lease
   Purpose: For reporting and regulatory compliance
   Output: Medallion Number
   ```

**Error Handling Strategy**:

- **No Vehicle Found**: Mark as Failed, reason = "No vehicle found for plate"
- **No Active Lease**: Mark as Failed, reason = "No active lease on transaction date"
- **No Driver**: Mark as Failed, reason = "No driver assigned to lease"
- **Database Error**: Mark as Failed, reason = specific error, rollback transaction

### Posting Logic - Detailed Theory

**Problem**: Create accurate financial records for toll charges.

**Double-Entry Accounting Principle**:
```
Debit (Charge): Driver owes money
Credit (Revenue): Company collects from driver
```

**For EZPass Module**:
- Create **Debit entry** in driver's ledger account
- This represents money driver owes to company
- Company will deduct from driver's earnings or collect separately

**Ledger Entry Components**:

1. **Identification**
   - Source Type: "EZPASS" (indicates origin of charge)
   - Source ID: Transaction ID (for traceability)
   - Reference Number: EZPass transaction ID

2. **Amounts**
   - Transaction Amount: Actual toll amount
   - Transaction Type: "Debit" (charge to driver)

3. **Associations**
   - Driver ID: Who pays
   - Vehicle ID: Which vehicle
   - Lease ID: Under which lease agreement
   - Medallion ID: For regulatory tracking

4. **Dates**
   - Transaction Date: When toll occurred
   - Posting Date: When recorded in system

5. **Description**
   - Human-readable description for statements
   - Example: "EZPass toll - MTA - ABC123"

**Validation Before Posting**:
- Transaction must be in "Associated" status
- All required IDs must be present
- Lease must still exist in system
- Amount must be positive

---

## 6. Design Patterns Used

### 1. Repository Pattern

**Intent**: Separate domain logic from data access logic

**Implementation**:
```
Application needs data → Calls Repository → Repository queries DB
                                        ← Returns domain objects
```

**Benefits**:
- Business logic doesn't contain SQL
- Can swap database implementations
- Easy to mock for testing
- Centralized data access logic

### 2. Dependency Injection

**Intent**: Achieve loose coupling between components

**Implementation**:
```python
# Service doesn't create its own repository
# Repository is "injected" by framework

class EZPassService:
    def __init__(self, repo: EZPassRepository = Depends(get_repository)):
        self.repo = repo  # Injected, not created
```

**Benefits**:
- Services don't depend on concrete implementations
- Easy to test with mocks
- Components can be swapped without code changes
- Follows SOLID principles

### 3. Strategy Pattern (Implicit)

**Intent**: Define family of algorithms, make them interchangeable

**Implementation**: Association logic can vary based on business rules

**Example**:
- Strategy A: Match by plate + date
- Strategy B: Match by plate + time window
- Strategy C: Match by tag ID + date

Current implementation uses Strategy A, but architecture allows easy addition of others.

### 4. Template Method (Implicit)

**Intent**: Define skeleton of algorithm, let subclasses override steps

**Implementation**: Processing operations follow template:

```
1. Get unprocessed records
2. For each record:
   a. Validate
   b. Process
   c. Update status
3. Create log entry
4. Return results
```

Association and Posting follow this template with different step implementations.

### 5. Factory Pattern (Implicit)

**Intent**: Create objects without specifying exact class

**Implementation**: Repository creates domain objects from database rows

**Benefits**:
- Encapsulates object creation logic
- Domain layer doesn't know about database details

### 6. Async/Await Pattern

**Intent**: Handle concurrent operations efficiently

**Implementation**:
```
Traditional (Blocking):
Request 1 → [Wait for DB] → Response 1
Request 2 →                    [Wait for DB] → Response 2

Async (Non-blocking):
Request 1 → [DB Operation (non-blocking)]
Request 2 → [DB Operation (non-blocking)]
         ↓                  ↓
      Response 1         Response 2
```

**Benefits**:
- Handle 1000+ concurrent requests
- Better resource utilization
- Faster response times
- Scalable architecture

---

## 7. Integration Architecture

### Database Integration

**Technology**: MySQL with async driver (asyncmy)

**Connection Management**:
```
Application Start → Create Connection Pool
                    ↓
Multiple Requests → Reuse Connections from Pool
                    ↓
Application End   → Close All Connections
```

**Benefits**:
- Connection pooling prevents connection exhaustion
- Async operations don't block on I/O
- Automatic reconnection on failures

### External Systems Integration

**Lease Management System**:
```
EZPass Module → Queries Lease Database → Gets Active Leases
              ← Returns Lease Details
```

**Ledger System**:
```
EZPass Module → Creates Ledger Entry → Posts to General Ledger
              ← Returns Confirmation
```

**Vehicle Registry**:
```
EZPass Module → Queries Vehicle DB → Matches Plate Numbers
              ← Returns Vehicle Info
```

### API Integration

**Authentication Flow**:
```
Client → Login API → JWT Token
      ← Token

Client → EZPass API (with Token) → Validates Token
                                  → Process Request
                                  ← Returns Response
```

**Request/Response Cycle**:
```
1. Client sends HTTP request
2. Authentication middleware validates JWT
3. Router receives request
4. Router calls Service with parameters
5. Service calls Repository for data
6. Repository queries Database
7. Database returns results
8. Repository transforms to domain objects
9. Service applies business logic
10. Service returns results
11. Router formats HTTP response
12. Client receives response
```

---

## 8. Error Handling Strategy

### Multi-Layer Error Handling

**Philosophy**: Fail gracefully, provide useful information, never expose internals

### Layer 1: Input Validation
```
Problem: Invalid file format, missing columns
Strategy: Validate early, fail fast
Action: Return 400 Bad Request with specific error
Example: "File validation failed: Missing required column 'Date'"
```

### Layer 2: Business Rule Violations
```
Problem: No active lease found, invalid associations
Strategy: Mark as failed, record reason, continue processing others
Action: Update transaction status, log detailed reason
Example: Transaction marked as Failed with reason "No active lease on transaction date"
```

### Layer 3: Database Errors
```
Problem: Connection lost, constraint violation, deadlock
Strategy: Rollback transaction, log error, return generic message
Action: Roll back changes, log full error with context
Example: Return 500 Internal Server Error, "Database operation failed"
```

### Layer 4: System Errors
```
Problem: Out of memory, service unavailable
Strategy: Log critical error, alert operations, return generic error
Action: System logs error with full stack trace
Example: Return 503 Service Unavailable
```

### Error Context Preservation

Every error includes:
- **What**: Description of what failed
- **Where**: Which component (Layer, Class, Method)
- **When**: Timestamp
- **Why**: Root cause if known
- **Context**: Related IDs (transaction_id, user_id, etc.)

### Structured Logging

```
Level: ERROR
Message: "Failed to associate transaction"
Context: {
    "transaction_id": 123,
    "plate_no": "ABC123",
    "transaction_date": "2025-10-11",
    "error": "No active lease found",
    "user_id": 456,
    "operation": "associate_transactions"
}
```

---

## 9. Performance Considerations

### Database Optimization

**Indexing Strategy**:
- Primary keys: Fast lookups
- Foreign keys: Join optimization
- Frequently filtered columns: plate_no, status, transaction_date
- Compound indexes: (status, transaction_date) for common queries

**Query Optimization**:
- Use `select()` instead of raw SQL for type safety
- Eager loading with `selectinload()` to avoid N+1 queries
- Pagination to limit result sets
- Proper WHERE clauses to leverage indexes

**Bulk Operations**:
- Import: Bulk insert 1000s of records at once
- Update: Batch updates instead of one-by-one
- Transaction management: Commit in batches

### Concurrency Handling

**Async Operations**:
- Multiple requests processed concurrently
- Non-blocking database operations
- Connection pool prevents resource exhaustion

**Race Condition Prevention**:
- Database transactions ensure atomicity
- Row-level locking for updates
- Optimistic concurrency with version fields (if needed)

### Scalability Design

**Horizontal Scaling**:
- Stateless service layer (can run multiple instances)
- Shared database with connection pooling
- Load balancer distributes requests

**Vertical Scaling**:
- Increase database connection pool size
- Optimize queries for large datasets
- Add database replicas for read operations

---

## 10. Security Architecture

### Authentication & Authorization

**JWT-Based Authentication**:
```
Login → Validate Credentials → Generate JWT Token
                               ↓
Every Request → Validate Token → Check Permissions
                                 ↓
Allow/Deny Access
```

**Role-Based Access Control**:
- Only authenticated users can access EZPass endpoints
- Audit trail tracks which user performed which operation
- API keys for automated imports (if needed)

### Data Security

**Input Validation**:
- Pydantic schemas validate all inputs
- Type checking prevents type-related vulnerabilities
- SQL injection prevented by ORM parameterization

**Sensitive Data**:
- Financial data encrypted at rest (database level)
- Secure connections (HTTPS/TLS)
- Audit logging for all changes

---

## Summary: Why This Architecture?

### Key Principles

1. **Separation of Concerns**: Each layer has one job
2. **Loose Coupling**: Components don't depend on implementation details
3. **High Cohesion**: Related functionality grouped together
4. **Testability**: Each layer can be tested independently
5. **Maintainability**: Easy to modify and extend
6. **Scalability**: Can handle growth in users and data
7. **Performance**: Async operations, proper indexing, connection pooling
8. **Reliability**: Comprehensive error handling, transaction management
9. **Security**: Authentication, authorization, input validation
10. **Observability**: Structured logging, audit trails

This architecture transforms a complex business process (toll management and driver billing) into a maintainable, scalable, and reliable software system.