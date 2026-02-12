# Thesis Structure Proposal: From Prototypes to Platform

This proposal restructures the thesis to focus on the **engineering journey**: transforming two disconnected, basic bachelor thesis projects into a unified, production-ready multi-cloud platform.

## Core Narrative Arc
1.  **The Starting Point**: Two isolated, limited prototypes (Optimizer & Deployer).
2.  **The Gap**: Why they couldn't simply be "glued" together (no state, no API, hardcoded, no specific cloud support).
3.  **The Solution**: A unified "Orchestrator" (Backend + UI) and deep refactoring of the legacy components.
4.  **The Result**: A seamless, end-to-end user experience.

---

## Proposed Chapter Structure

### 1. Introduction
*Set the stage and hook the reader.*
- **1.1 Motivation**: The need for multi-cloud Digital Twins (cost, resilience).
- **1.2 Problem Statement**: Existing tools are fragmented. We have theoretical cost models (from Bachelor Thesis A) and basic deployment scripts (from Bachelor Thesis B), but no way to use them together efficiently.
- **1.3 Research Objective**: To design and implement a *unified platform* that bridges the gap between theoretical cost optimization and practical infrastructure deployment.
- **1.4 Contributions**:
    - Refactoring and "API-fication" of legacy optimization code.
    - Transformation of static Terraform scripts into a dynamic Deployment Engine.
    - Creation of a new Orchestration Layer (Management API + Flutter UI).
    - Validation of the end-to-end flow.

### 2. Background
*The theoretical foundation (keep existing concepts).*
- **2.1 Digital Twins & The 5-Layer Architecture** (EDT_25 context).
- **2.2 Cloud Computing Implementation**:
    - Multi-cloud vs. Hybrid cloud.
    - Infrastructure as Code (Terraform).
- **2.3 Cost Optimization Theory**:
    - Mathematical models for cloud costs.
    - The complexity of cross-provider pricing.
- **2.4 Software Design Patterns**:
    - Brief introduction of the architecturally significant patterns used in this work.
    - Only patterns that directly solved a problem described in the thesis (to be identified during writing).
    - % TODO: Identify the relevant cross-cutting patterns from the codebase together with the user.

### 3. Analysis of Legacy Systems (NEW)
*Critique the starting point to justify your work.*
- **3.1 Overview of Legacy Prototypes**:
    - **Project A (The Brain)**: A cost calculation tool, not covering all cloud resources/services available now. No design patterns used — hardcoded calculations in large monolithic functions.
    - **Project B (The Muscle)**: A hardcoded Python SDK script, AWS-only, which worked in that single constellation. No patterns used, all values/credentials/file paths were hardcoded. Accessible only via CLI, stateless.
- **3.2 Gap Analysis**:
    - **Lack of Integration**: No common data format or API to connect A and B.
    - **State Management**: No database to track deployments (fire-and-forget).
    - **Usability**: CLI-only, requiring manual JSON editing.
    - **Flexibility**: Hardcoded values (regions, instance types) preventing real-world use.
- **3.3 Requirements for a Unified Platform**:
    - Need for a "Manager" to hold state.
    - Need for standardization (Docker, APIs).
    - Need for a User Interface to visualize the "Twin".

### 4. System Architecture (The "To-Be" State)
*The blueprint of what you built.*
- **4.1 High-Level Design**:
    - The **Orchestrator** (New): Central hub, API, UI.
    - The **Brain** (Refactored): Stateless calculation service ("Microservice").
    - The **Muscle** (Refactored): Stateful deployment engine.
- **4.2 Data Flow & State Management**:
    - % TODO: Detail the data flow and state management design (to be elaborated later).
    - The Optimizer and Deployer still operate on files (not a database) — the Deployer in particular requires actual files because Terraform works on `.tf` files and state files.
    - The Orchestrator (Management API) uses a SQL database for persisting twin configurations and deployment state — bridging the file-based subsystems.
- **4.3 Technology Stack Decisions**:
    - Docker/Docker Compose for unified dev environment.
    - Python (FastAPI/Flask) for backend services.
    - Flutter for the frontend (Why Flutter? Cross-platform, reactive).

### 5. Implementation & Refactoring (CORE CHAPTER)
*The "Meat" of the thesis - how you did it.*

> **Critical aspect**: One of the most critical parts was rebuilding the Digital Twin architecture from single-cloud AWS to multi-cloud (AWS, Azure, GCP). This involved comparing cloud services across providers and planning the multi-cloud DT architecture. Many production-ready design decisions were intentionally simplified to keep the thesis scope manageable (e.g., using direct HTTP calls between cloud functions instead of an event handler for the data flow, or choosing cheaper service workarounds since the optimizer currently only calculates cost optimization).
- **5.1 Standardization Phase**:
    - Containerizing the legacy projects (Dockerfiles).
    - Establishing a shared development environment (`docker-compose`).
    - Standardizing configuration (Environment variables vs. hardcoded strings).
- **5.2 Refactoring Methodology**:
    - Since the legacy code lacked architecture and design patterns, the first step was a deep structural refactoring for maintainability, extendability, and scalability — effectively turning the code completely upside down.
    - Quick-and-dirty adaptation was attempted first, but abandoned because it introduced too many bugs.
    - After the structural refactoring, multi-cloud content was added. During this process, additional parts continuously surfaced that also required pattern application to avoid opening up new potential bugs.
    - This was an iterative cycle: refactor → extend → discover more code needing patterns → refactor again.
- **5.3 Refactoring "The Brain" (Optimizer)**:
    - **Challenge 1**: Applying the cost calculation formulas to new cloud services and making them comparable across providers. Cloud providers intentionally use incomparable pricing metrics (e.g., gibibytes vs. gigabyte-seconds), making cross-provider cost comparison extremely difficult.
    - **Challenge 2**: Fetching correct dynamic pricing data (the original project used hardcoded pricing values). Provider pricing APIs return long descriptive strings requiring parsing to extract values and metrics, which vary in unit granularity (per unit, per million, per 10k, etc.).
    - **Solution**: Implementing provider-specific price fetchers that normalize pricing into comparable units.
    - **Patterns applied**: % TODO: Identify specific patterns used in the Optimizer refactoring.
- **5.4 Refactoring "The Muscle" (Deployer)**:
    - **Challenge**: The original project used the Python AWS SDK. Attempting to extend this approach to multi-cloud immediately led to dependency loops and race conditions during deployment. It was impossible to correctly manage all resource dependencies in this large construct using SDK calls.
    - **Decision**: Switched to Terraform, which handles resource dependencies and deploys in the correct order automatically.
    - **Challenge**: Managing Terraform state in a containerized environment.
    - **Solution**: State file management and isolation.
    - **Patterns applied**: % TODO: Identify specific patterns used in the Deployer refactoring.
- **5.5 Building "The Orchestrator" (New Work)**:
    - **Backend**: Implementing the Management API to coordinate Brain and Muscle.
    - **Frontend**: Building the Flutter UI (Wizard flow, Drag-and-drop elements).
    - **Integration**: Connecting the pieces (Dealing with async deployments, SSE for logs).

### 6. Evaluation
*Prove it works.*
- **6.1 Functional Validation**: E2E tests proving the flow works (UI -> Cloud Resources).
- **6.2 Deployment Performance**: Metrics on provisioning time.

### 7. Discussion
- **7.1 Challenges Encountered**:
    - "Dependency Hell" in legacy Python projects.
    - Terraform state locking issues.
    - Cross-cloud networking complexities.
- **7.2 Comparison**: Old manual process vs. New automated process.
- **7.3 Limitations**: What is still missing?

### 8. Conclusion
- Summary and Future Work.

---

## Next Steps
If you approve this structure, I will:
1.  **Backup** your current `chapters/` folder.
2.  **Create new .tex files** for the new chapters (e.g., `legacyAnalysis.tex`, `orchestratorImplementation.tex`).
3.  **Fill them with detailed prompts** (comments) based on this outline so you can start writing.
