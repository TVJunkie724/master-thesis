# TODOs

- [x] add force update params for fetch regions endpoints
- [x] add more detailed documentation for endpoints (to view in swagger)
- [x] update docs (testing?, api reference, ...)

- [x] update docs for api reference
- [x] update example_input.json

- [ ] get into implementation of changes for calculation engine
    - [x] add new services (supporter services) to engine
    - [x] define new params for calculation engine
    - [x] update ui and params with new inputs
    - [x] update cards in ui
    - [x] adapt coloring in cheapest path in ui (after calculation)
    - [x] for google twinmaker and grafana, add info that services are self-hosted 

- [x] run and fix tests
- [x] update docs (with changes in pricing calculations, web ui, rest api, architecture? and concerning deployment roadmap)
- [x] update architecture section in ui

!!! IMPORTANT: !!!
- [x] adapt ui and validation of inputs: trigger workflow, return feedback to device and corresponding fields are dependent on useEventChecking = true!!!

## flutter later
- [ ] add section after header with buttons for fetching up-to-date prices and regions??? on page load, the age of the json files should be shown, for the user to decide if he wants to update them or not
- [ ] let the user decide after calculation, if he wants to stick with GCP (if even chosed via calculation engine) or switch to another provider