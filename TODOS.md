# TODOs

## Deployer

- [ ] in deployment roadmaps, consider multi-cloud deployment, and functions to let layers interact with each other
    - [ ] dont forget checks for permissions, and information, which permissions / keys / tokens are needed for each layer and where to add them (e.g. for a function in the env variables)

- [ ] copy new version of deployer from !!3-cloud-deployer to 3-cloud-deployer and make adaptions as in 3-cloud-deployer now
    - [ ] add params for provider, to select which service to deploy on which provider (per layer)
    - [ ] separate calls for deploying layers, atm only one call for deploy and only one provider is used
    - [ ] adapt rest_api.py and cli calls to the new version
    - [ ] atm state machines are hard coded in python files. read definitions from json files
    - [ ] include config_providers.json in the new deployer version, to decide which provider to use for each layer (json file generated in cost optimizer project)

- [ ] generate example functions for azure and google, like the template functions now existing in aws

- [ ] dont forget to update docs
- [ ] add tests

# cost optimizer

- [ ] update pricing.json (being the template) to full structure as defined in aws/azure/google pricing docs

- [ ] update implementation of fetching aws services pricing for new services (see aws pricing docs)
- [ ] update implementation of fetching azure services pricing for new services (see azure pricing docs)
- [ ] add implementation of fetching gcp services pricing for new services (see gcp pricing docs)

- [ ] update web ui with further conditions (plan tbd)
- [ ] update rest api request body after ui changes

- [ ] dont forget to update docs
- [ ] need additional tests?