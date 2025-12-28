# Integration To-Do List

Derived from [Project Vision: Twin2MultiCloud](integration_vision.md).

## 1. Core Platform Development
- [ ] **CLI Development** (`twin2multicloud_cli`)
    - [ ] Implement command for executing optimization workflows.
    - [ ] Implement command for triggering deployment workflows.
- [ ] **Frontend Development** (`twin2multicloud_flutter`)
    - [ ] Create interactive scenario modeling interface.
    - [ ] Create cost comparison visualization.
    - [ ] Implement deployment trigger interface.

## 2. System Architecture Integration
- [ ] **Orchestrator Logic**
    - [ ] Implement "Brain" consumption logic (Optimizer integration).
    - [ ] Implement "Muscle" control logic (Deployer integration).
    - [ ] Manage user session and configuration state.
- [ ] **Optimizer Integration** (`2-twin2clouds`)
    - [x] Ensure `cloud_price_fetcher` modules are integrated and fetching real-time data.
    - [ ] Verify optimization output format is compatible with Orchestrator/Deployer.
- [ ] **Deployer Integration** (`3-cloud-deployer`)
    - [ ] Implement input parsing for optimal configuration from Orchestrator.
    - [ ] Automate cross-cloud "plumbing" (Pub/Sub to Lambda triggers, etc.).

## 3. Management Platform & Backend
- [ ] **Backend Infrastructure**
    - [ ] Set up persistent database (profiles, credentials, configs, state).
    - [ ] Implement Authentication (OAuth: Google/Microsoft/University).
    - [ ] Containerize Management Backend alongside Deployer.
- [ ] **User Workflow Implementation**
    - [ ] **Configuration & Optimization**
        - [ ] Implement data fetching status logs (Real-time).
        - [ ] Implement manual cloud choice override with cost warnings.
    - [ ] **Deployment**
        - [ ] Implement granular deployment options (Deploy L1, L2, etc.).
        - [ ] Implement real-time deployment log streaming (WebSocket/Stream).
    - [ ] **Operation & Monitoring**
        - [ ] Create "Twin List" view.
        - [ ] Develop Twin Dashboard:
            - [ ] Live Health Status.
            - [ ] Real-time Error/Warning Log (e.g., L2 Connector Timeout).
            - [ ] Embed Grafana visualization.
            - [ ] Add destruction/re-deployment options.
            - [ ] Implement Real-time Cost/Billing tracking.
            - [ ] Display full user specifications/configs.
- [ ] **Error Handling Strategy**
    - [ ] Implement critical error publishing to centralized Error Notification Topic/API.
    - [ ] Subscribe Management Backend to Error Topic.
    - [ ] Push alerts to Flutter App.

## 4. Future Roadmap & Validation
- [ ] **Unified API**
    - [ ] Expose Optimizer as a microservice.
    - [ ] Expose Deployer as a microservice.
- [ ] **Validation**
    - [ ] Collect real-world cost data from deployed twins.
    - [ ] Validate theoretical formulas against gathered data.
