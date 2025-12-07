# TODOs

- [x] refactor rest_api.py into multiple files
- [x] refactor / better structure constants.py (for better readability, organization and maintainability)
- [x] refactor validation logic to validator.py and add coverage

- [x] check upload endpoints, it should be possible to either upload a binary or base64 encoded string or a file by filepath? is filepath feasable? dont forget to update description on endpoint change
- [x] implement TODO functions in AWS roadmap, use roadmap, project code base and technical_specs.md as reference
- [x] check all lambda functions for additional error handling
- [x] split core deployer by layer into separate files
- [ ] make device simulator adaptable by user? which part of the code / the files can be moved to /upload/project_name directory
- [ ] OPTIONAL: implement error handling with optional parameters (check if implemented in cost optimizer first)

- [x] update documentation for all changes
- [x] let claude opus search for bugs in whole project

- [ ] for validation endpoints, maybe add get endpoints for most of them to also check existing files in the project (config files, functions, ...? )
- [ ] when uploading the zip file, the project structure is extended with its contents, but i would also like to save the whole zip file (with timestamp in naming, in case a new version is uploaded) in the upload/project_name directory
- [ ] there should be further endpoints to download the iot devices configuration files (payload, certificates, etc, whatever is needed to run the simulator manually somewhere else)
- [ ] investigate which permissions in the aws cloud are required to fulfill the full requirements of the deployer
    - [ ] add endpoint to check which permissions are given for the given user (using given credentials)

- [ ] swagger fastapi dark theme? fastapi-swagger-dark package?