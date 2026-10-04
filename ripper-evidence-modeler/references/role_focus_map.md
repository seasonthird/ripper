# Role Focus Map

Use this file after confirming `{目标岗位方向}`. Select evidence and wording that matches the role. Do not force unrelated signals into the resume.

## 后端工程师

Prioritize:

- API design
- Data model
- Status transition
- Task queue
- Cache
- Concurrency
- Async task
- Permission
- Log and monitor
- Stability
- Performance optimization
- Engineering maintainability

De-emphasize:

- Ordinary page features
- Simple API calls
- CRUD without complex logic

## AI 应用开发 / AI Agent 工程师

Prioritize:

- Agent workflow
- Planner / Executor / Verifier or other responsibility separation
- Tool calling
- Tool selection
- MCP, Skill, tool registry, and capability governance
- Multi-step task execution
- RAG
- Retrieval evaluation, reranking, and fallback
- Memory, prompt, context, and token-budget management
- DAG orchestration
- Task planning
- Sandbox isolation and safe code/tool execution
- Human approval, permission boundaries, and guardrails
- Model gateway, multi-model routing, and structured output
- External system integration such as Kubernetes, databases, observability, or business APIs
- Evaluation and tuning
- Token cost optimization
- TTFT / latency optimization
- Trace and observability

De-emphasize:

- Simple prompt wrapper
- Single-turn QA
- Only calling LLM APIs
- Chatbot without task orchestration logic
- Naming a Skill, Agent, RAG, or sandbox without explaining its actual mechanism

## 云原生 / FaaS 工程师

Prioritize:

- Function packaging
- Task scheduling
- Elastic execution
- Cold start
- Distributed execution
- Resource orchestration
- Cloud-edge collaboration
- DAG execution
- Serverless deployment
- Execution status tracking
- Failure retry

De-emphasize:

- Generic deployment description
- Only "used Docker"
- Only "deployed to cloud server"

## 平台开发工程师

Prioritize:

- Platform capability abstraction
- Configuration
- Plugin system
- Multi-tenancy
- Permission
- Task management
- Logs
- Monitoring
- Audit
- Reusable components
- Developer toolchain

De-emphasize:

- Single business feature
- Static configuration page
- Management backend without abstraction

## 算法工程师

Prioritize:

- Modeling method
- Data processing
- Retrieval
- Ranking
- Recommendation
- Planning
- Optimization algorithm
- Experiment design
- Metric evaluation
- Ablation study
- Model effect analysis

De-emphasize:

- Only "called a model"
- No experiment result
- No metric
- No data or method explanation

## 数据工程师

Prioritize:

- Data pipeline
- Batch or stream processing
- Data model and schema design
- ETL/ELT
- Data quality checks
- Scheduling and dependency management
- Partitioning, indexing, and query optimization
- Data warehouse or lakehouse modeling
- Lineage, monitoring, and alerting
- Cost and resource optimization

De-emphasize:

- Only writing SQL without business or data-model context
- Simple dashboard configuration
- Data import/export without quality, scale, or scheduling details

## 前端工程师

Prioritize:

- Component abstraction
- State management
- Rendering performance
- Data flow and API integration
- Form validation and error handling
- Permission-aware UI
- Frontend engineering and build optimization
- Accessibility and compatibility
- Testing, mock data, and component documentation

De-emphasize:

- Static pages without interaction or engineering complexity
- Only adjusting style or layout
- Listing framework names without component or state logic

## 全栈工程师

Prioritize:

- End-to-end feature design
- API contract and data model
- Frontend-backend integration
- Permission and authentication flow
- State transition across UI and backend
- Error handling and observability
- Testing and deployment workflow
- Cross-layer performance or maintainability improvements

De-emphasize:

- Only saying "frontend and backend development"
- Separate stack lists without integrated feature logic
- Broad ownership claims without module boundaries

## DevOps / SRE 工程师

Prioritize:

- CI/CD pipeline
- Infrastructure as code
- Release automation
- Monitoring, alerting, and logging
- Reliability and incident response
- Capacity, resource, and cost optimization
- Container orchestration
- Environment management
- Rollback, health check, and deployment safety

De-emphasize:

- Only "used Docker" or "deployed server"
- Manual deployment steps without automation or reliability value
- Generic operation notes without measurable or observable effect

## 测试开发工程师

Prioritize:

- Test framework design
- Automated test cases
- E2E, integration, and API testing
- Mock, fixture, and test data management
- Coverage and quality gates
- CI integration
- Defect localization and regression prevention
- Performance, stability, or compatibility testing

De-emphasize:

- Only manual testing
- Only writing test cases without automation, coverage, or defect value
- Broad quality claims without test scope or evidence

## 产品经理

Prioritize:

- User scenario and problem framing
- Requirement decomposition
- Metric definition
- Workflow design
- Prioritization logic
- Cross-team collaboration
- Launch or validation evidence when provided by user

De-emphasize:

- Technical implementation details not tied to product decision
- Unsupported claims about growth or impact

## Other User-Specified Direction

Map the user's role wording to the closest capability cluster. If unsure, ask one concise follow-up question before finalizing.
