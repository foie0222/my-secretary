# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LINE Agent Secretary is an AI-powered personal assistant accessible via LINE messaging app. The system integrates with Google Calendar using AWS AgentCore Runtime, AgentCore Gateway, and AgentCore Identity for OAuth management.

### Key Technologies
- **Language**: Python 3.12
- **Package Manager**: uv
- **Agent Framework**: Strands Agents (planned)
- **Infrastructure**: AWS CDK
- **AI Model**: Claude Sonnet 4.5 (global inference profile)
- **AWS Services**: AgentCore Runtime, AgentCore Gateway, AgentCore Identity, Lambda, Secrets Manager, ECR, API Gateway

## Development Commands

### Package Management
```bash
# Install all dependencies
uv sync

# Install with CDK infrastructure dependencies
uv sync --extra infra

# Install with dev dependencies (pytest, black, ruff, mypy)
uv sync --extra dev
```

### Code Quality
```bash
# Format code with Black
black .

# Lint with Ruff
ruff check .

# Type check with mypy
mypy .
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov

# Run specific test file
pytest tests/test_specific.py

# Run specific test function
pytest tests/test_specific.py::test_function_name
```

### Local Development
```bash
# Run AgentCore Runtime server locally
cd agent
python server.py
# Server runs on http://localhost:8080
```

### Infrastructure (CDK)
```bash
cd infra

# Bootstrap CDK (first time only)
cdk bootstrap

# Synthesize CloudFormation templates
cdk synth

# Deploy all stacks
cdk deploy --all

# Deploy specific stack
cdk deploy LineAgentLambdaStack

# Destroy stacks
cdk destroy --all
```

### Docker (for AgentCore Runtime)
```bash
# Build Docker image locally
cd agent
docker build -t line-agent-secretary .

# Build for ARM64 (required for AgentCore Runtime)
docker buildx build --platform linux/arm64 -t line-agent-secretary .
```

## Architecture

### Component Structure

The project follows a clear separation between different concerns:

1. **agent/** - AgentCore Runtime container
   - `server.py`: HTTP server with /ping, /invocations endpoints for AgentCore Runtime
   - `config.py`: Configuration management
   - `Dockerfile`: Container image for AgentCore Runtime (ARM64)

2. **functions/** - AWS Lambda functions
   - `calendar/operations.py`: Google Calendar CRUD operations using AgentCore Identity
   - `line_webhook/handler.py`: LINE webhook Lambda handler (invokes AgentCore Runtime)
   - `common/utils.py`: Shared utilities

3. **infra/** - AWS CDK infrastructure as code
   - `app.py`: CDK app entry point, orchestrates all stacks
   - `stacks/`:
     - `secrets_stack.py`: Secrets Manager for LINE credentials
     - `github_oidc_stack.py`: GitHub OIDC for GitHub Actions → ECR deployment
     - `lambda_stack.py`: Calendar operations Lambda function
     - `agentcore_stack.py`: AgentCore Gateway and Runtime IAM roles
     - `line_webhook_stack.py`: LINE webhook Lambda + API Gateway

### Authentication Flow

The system uses AWS AgentCore Identity for secure OAuth2 token management:

1. **Google OAuth Setup**: OAuth2 credentials configured via AgentCore Identity Credential Provider
2. **Token Isolation**: Lambda functions never handle refresh tokens directly
3. **AgentCore Identity**: Manages token lifecycle (refresh, expiration) automatically
4. **Workload Identity**: Each user gets isolated token access via workload identity

Key code pattern in `functions/calendar/operations.py`:
```python
async def get_google_access_token(user_id: str = "default-user") -> str:
    # Step 1: Get workload access token
    workload_access_token = identity_client.get_workload_access_token(
        workload_name=WORKLOAD_NAME,
        user_id=user_id
    )

    # Step 2: Exchange for OAuth token
    token_response = await identity_client.get_token(
        credential_provider_name=CREDENTIAL_PROVIDER_NAME,
        workload_access_token=workload_access_token
    )

    return token_response["access_token"]
```

### Deployment Architecture

1. **GitHub Actions** (.github/workflows/deploy.yml):
   - Triggered on push to master or changes in agent/
   - Uses GitHub OIDC to authenticate with AWS (no long-lived credentials)
   - Builds ARM64 Docker image for AgentCore Runtime
   - Pushes to ECR
   - AgentCore Runtime auto-pulls new images

2. **AgentCore Runtime**:
   - Runs agent Docker container (agent/server.py)
   - Exposes /ping (health check) and /invocations (agent invocation)
   - LINE webhook Lambda → invokes Runtime → generates AI response via Bedrock

3. **AgentCore Gateway**:
   - Provides MCP (Model Context Protocol) interface
   - Connects Lambda functions (calendar operations) as targets
   - Uses IAM-based authorization
   - Tool schemas defined in `agentcore_stack.py`

### CDK Stack Dependencies

```
SecretsStack (LINE credentials)
  ↓
LambdaStack (calendar operations) ← GitHubOIDCStack (CI/CD)
  ↓
AgentCoreStack (Gateway + Runtime roles)
  ↓
LineWebhookStack (API Gateway + Webhook Lambda)
```

## Important Configuration

### Environment Variables

**Agent Runtime** (agent/server.py):
- `LINE_CHANNEL_SECRET`: LINE channel secret
- `LINE_CHANNEL_ACCESS_TOKEN`: LINE channel access token
- `CALENDAR_LAMBDA_ARN`: **Required** - ARN of the calendar operations Lambda function (obtain from CDK output: `CalendarFunctionArn`)
- `AWS_REGION`: AWS region (default: ap-northeast-1)
- `PORT`: Local server port (default: 8000)

**Calendar Lambda** (functions/calendar/operations.py):
- `WORKLOAD_NAME`: AgentCore Identity workload name (default: "line-agent-secretary")
- `CREDENTIAL_PROVIDER_NAME`: OAuth2 credential provider name (default: "google-calendar-provider")
- `AWS_REGION`: AWS region (default: ap-northeast-1)

### Hard-coded Runtime ID

The AgentCore Runtime ID is hard-coded in `infra/app.py`:
```python
agent_runtime_id="line_agent_secretary-Z8wcZvH0aN"
```

If creating a new Runtime, update this value in app.py.

### CDK Context

Region and account can be configured via CDK context in `infra/cdk.json` or passed as parameters.

## Tool Schemas for AgentCore Gateway

The Google Calendar operations exposed via AgentCore Gateway are defined in `infra/stacks/agentcore_stack.py` in the `_create_calendar_tool_schemas()` method:

1. **list_calendar_events**: Get calendar events (time_min, time_max, max_results)
2. **create_calendar_event**: Create event (summary, start_time, end_time, description, location)
3. **update_calendar_event**: Update event (event_id, summary, start_time, end_time, description, location)
4. **delete_calendar_event**: Delete event (event_id)

When adding new calendar operations, update both:
1. Lambda function in `functions/calendar/operations.py`
2. Tool schema in `infra/stacks/agentcore_stack.py`

## Manual Setup Steps

Some AWS resources cannot be fully automated with CDK and require manual setup:

1. **Google OAuth2 Credential Provider** (via AWS CLI):
   ```bash
   aws bedrock-agentcore-control create-oauth2-credential-provider \
     --region ap-northeast-1 \
     --name "google-calendar-provider" \
     --credential-provider-vendor "GoogleOauth2" \
     --oauth2-provider-config-input '{"googleOauth2ProviderConfig": {...}}'
   ```

2. **LINE Credentials** (via AWS CLI):
   ```bash
   aws secretsmanager update-secret \
     --secret-id line-agent-secretary/line-credentials \
     --secret-string '{"channel_secret": "...", "channel_access_token": "..."}'
   ```

3. **LINE Webhook URL**: Set API Gateway webhook URL in LINE Developers Console

Refer to README.md for detailed setup instructions.

## Known Issues and Patterns

### AgentCore Identity Decorator Pattern

The `@requires_access_token` decorator is used in `functions/calendar/operations.py` for automatic token injection. However, `list_calendar_events` uses a manual pattern instead:

```python
# Manual pattern (list_calendar_events)
access_token = await get_google_access_token(user_id)
creds = Credentials(token=access_token, scopes=SCOPES)

# Decorator pattern (create/update/delete)
@requires_access_token(provider_name="...", scopes=SCOPES, auth_flow="USER_FEDERATION")
async def operation(*, access_token: str):
    creds = Credentials(token=access_token, scopes=SCOPES)
```

When adding new operations, prefer the decorator pattern for consistency.

### Lambda Handler Operation Routing

The Lambda handler in `functions/calendar/operations.py` routes operations via the `operation` field:
```python
operation = event.get("operation")  # "list", "create", "update", "delete"
params = event.get("parameters", {})
```

Ensure AgentCore Gateway invocations include the correct operation field.

### Timezone Handling

Calendar events use hardcoded timezone "Asia/Tokyo" in `functions/calendar/operations.py`. Update if supporting multiple timezones.

## Tool Integration Implementation

### How Calendar Tools Work

The agent integrates with Google Calendar using a tool-calling approach:

1. **Tool Definition** (agent/server.py:58-158): Four calendar tools are defined with Anthropic's tool schema format:
   - `list_calendar_events`: Get calendar events
   - `create_calendar_event`: Create new events
   - `update_calendar_event`: Update existing events
   - `delete_calendar_event`: Delete events

2. **Tool Execution Loop** (agent/server.py:248-367):
   - Claude receives user message with `tools` parameter
   - When Claude returns `stop_reason="tool_use"`, the agent extracts tool calls
   - `execute_calendar_tool()` function invokes the calendar Lambda function
   - Tool results are returned to Claude to generate final response
   - Loop continues until Claude returns `stop_reason="end_turn"`

3. **Lambda Invocation** (agent/server.py:176-232):
   - Tool names are mapped to Lambda operations (`list`, `create`, `update`, `delete`)
   - boto3 Lambda client invokes the calendar function with operation + parameters
   - Lambda function uses AgentCore Identity for OAuth token management

### Adding New Tools

To add new calendar operations or integrate other services:

1. Add tool definition to `CALENDAR_TOOLS` array (or create new tool array)
2. Update `execute_calendar_tool()` to handle new tool names
3. Implement Lambda function for the new operation
4. Update CDK to deploy new Lambda function
5. Grant Runtime IAM role permission to invoke the new Lambda function
