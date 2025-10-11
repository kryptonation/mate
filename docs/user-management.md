## **User Management Module Documentation**

### 1. Overview

The User Management module is the foundational component for authentication, authorization, and user data administration in the application. It has been completely modernized to be fully asynchronous, highly performant, and secure, serving as a blueprint for refactoring other modules.

**Key Features:**
*   **Asynchronous Operations**: All API endpoints and database interactions are non-blocking, ensuring high throughput for I/O-bound tasks.
*   **Robust Authentication**: Implements a standard JWT-based system with access and refresh tokens.
*   **Role-Based Access Control (RBAC)**: Provides a flexible and secure way to control access to different parts of the application.
*   **Clean, Decoupled Architecture**: Utilizes modern design patterns (Repository, Service, Dependency Injection) for maintainability and testability.
*   **Complete User Lifecycle Management**: Includes endpoints for user search, login, password changes, and role administration.

---

### 2. Architecture & Design Patterns

The module is built on a clean, multi-layered architecture that separates concerns, making the code easy to understand, test, and extend.

**Flow of a Request:**
`Client -> Router -> Service -> Repository -> Database`

1.  **Asynchronous Stack (FastAPI & SQLAlchemy)**
    *   All API endpoints are defined with `async def`, allowing FastAPI to handle requests concurrently without blocking.
    *   Database sessions are managed by an asynchronous dependency (`get_async_db`), and all database queries are performed with `await`, preventing the application from stalling on database I/O.

2.  **Repository Pattern**
    *   **Purpose**: To decouple the business logic from the data access logic. The service layer does not know *how* data is fetched or stored; it only knows that it can request data from the repository.
    *   **Implementation**: The `UserRepository` (`app/users/repository.py`) contains all SQLAlchemy query code. It is responsible for all interactions with the `users` and `roles` tables.
    *   **Benefit**: If we ever wanted to switch our database or ORM, we would only need to change the repository. The service layer, containing the core business rules, would remain untouched. It also makes testing easier, as we can "mock" the repository.

3.  **Service Layer**
    *   **Purpose**: To contain all business logic. It orchestrates data flow and enforces rules.
    *   **Implementation**: The `UserService` (`app/users/services.py`) handles tasks like verifying passwords, checking platform rules on login, and constructing user objects. It calls the `UserRepository` to fetch and persist data.
    *   **Benefit**: Keeps the API router clean and focused only on handling HTTP requests and responses.

4.  **Dependency Injection (DI)**
    *   **Purpose**: FastAPI's DI system automatically provides necessary dependencies (like database sessions or service instances) to our endpoint functions.
    *   **Implementation**: We use `Depends()` to inject `UserService`, `get_current_user`, and the `RoleChecker`. For example: `def my_endpoint(user_service: UserService = Depends())`.
    *   **Benefit**: This removes the need for global objects, promotes loose coupling, and makes our code more explicit and easier to test.

### 3. File & Code Structure Breakdown

*   **`models.py`**: Defines the SQLAlchemy data models for `User` and `Role` using the modern 2.x `Mapped` and `mapped_column` syntax for improved type safety. This file is the single source of truth for the database schema.

*   **`schemas.py`**: Defines the Pydantic models for API data validation and serialization. This file acts as the "API contract," clearly defining the expected shape of requests and responses. It includes schemas for login, user creation/updates, password changes, and paginated user lists.

*   **`repository.py`**: The Data Access Layer. The `UserRepository` class exclusively handles all `select`, `insert`, and `update` operations for users and roles. It is fully asynchronous.

*   **`services.py`**: The Business Logic Layer. The `UserService` class orchestrates user-related operations. It uses the `UserRepository` (provided via DI) to interact with the database and contains logic that doesn't belong in the router or repository, such as password verification.

*   **`utils.py`**: Contains core utilities for security and authorization.
    *   `get_current_user`: An async dependency that verifies a JWT from the `Authorization` header and returns the corresponding `User` object from the database. It's used to protect endpoints and identify the active user.
    *   `RoleChecker`: A powerful, reusable class-based dependency for implementing RBAC. You can protect an endpoint by simply adding `Depends(RoleChecker(["Admin"]))` to its signature.

*   **`router.py`**: The API Layer. This file defines all the HTTP endpoints (e.g., `POST /login`, `GET /users`). It is responsible for receiving requests, calling the appropriate service methods, and returning responses. It remains lean, with all complex logic delegated to the service layer.

---

### 4. API Endpoint Reference

#### Authentication

| Endpoint | Method | Description | Authentication |
| :--- | :--- | :--- | :--- |
| `/login` | `POST` | Authenticates a user with email and password. | Public |
| `/refresh` | `POST` | Issues a new access token using a valid refresh token. | Refresh Token |
| `/user/me` | `GET` | Retrieves the profile of the currently logged-in user. | Access Token |

#### Password Management

| Endpoint | Method | Description | Authentication |
| :--- | :--- | :--- | :--- |
| `/users/change-password` | `POST` | Allows an authenticated user to change their own password. | Access Token |

#### User Search & Management (RBAC Protected)

| Endpoint | Method | Description | Permissions |
| :--- | :--- | :--- | :--- |
| `/users` | `GET` | Searches for users with pagination, filtering, and sorting. | Admin, Manager |

#### Role Management (RBAC Protected)

| Endpoint | Method | Description | Permissions |
| :--- | :--- | :--- | :--- |
| `/roles` | `GET` | Lists all roles available in the system. | Admin, Manager |
| `/roles` | `POST` | Creates a new role. | Admin |

---

### 5. Security & Authorization (RBAC)

Security is implemented at multiple levels:

1.  **Password Hashing**: Passwords are never stored in plain text. They are securely hashed using `bcrypt` via the `passlib` library (`app/utils/security.py`).

2.  **JWT Authentication**:
    *   Upon successful login, the server issues a short-lived **access token** and a long-lived **refresh token**.
    *   The access token must be sent in the `Authorization: Bearer <token>` header for all protected requests.
    *   When the access token expires, the client can use the refresh token to get a new one without requiring the user to log in again.

3.  **Role-Based Access Control (RBAC)**:
    *   Access to sensitive endpoints is controlled by the `RoleChecker` dependency (`app/users/utils.py`).
    *   **How it works**: You create an instance of the class with a list of roles that are allowed to access an endpoint.
        ```python
        # Example: Only users with the "Admin" role can access this.
        allow_admin = RoleChecker(["Admin"])

        @router.post("/roles", dependencies=[Depends(allow_admin)])
        async def create_role(...):
            ...
        ```
    *   If the currently authenticated user does not have one of the required roles, the request is automatically rejected with a `403 Forbidden` error. This provides a simple, declarative, and highly secure way to manage permissions.

---

### 6. How to Use & Extend

This modernized module is designed to be easy to extend.

**Example: Adding a new "Deactivate User" endpoint (Admin only)**

1.  **Update the Repository (`repository.py`)**: The repository already has a generic `update` method, so no changes are needed here. If it were a more complex operation (like a hard delete), you would add a new `async def delete_user(...)` method.

2.  **Update the Service (`services.py`)**: Add the business logic.

    ```python
    # In UserService class
    async def deactivate_user(self, user_id: int) -> User:
        user_to_deactivate = await self.repo.get_user_by_id(user_id)
        if not user_to_deactivate:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        user_to_deactivate.is_active = False
        return await self.repo.update(user_to_deactivate)
    ```

3.  **Add the Endpoint to the Router (`router.py`)**: Create the new endpoint and protect it with the `RoleChecker`.

    ```python
    # In router.py
    @router.put("/users/{user_id}/deactivate", response_model=UserResponse, dependencies=[Depends(allow_admin)])
    async def deactivate_user(
        user_id: int,
        user_service: UserService = Depends()
    ):
        """Deactivate a user account (Admin only)."""
        deactivated_user = await user_service.deactivate_user(user_id)
        return deactivated_user
    ```

This clear, three-step process (Repository -> Service -> Router) ensures that new features are added in a way that is consistent, maintainable, and secure.