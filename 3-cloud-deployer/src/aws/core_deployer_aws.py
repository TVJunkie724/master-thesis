"""
Core Deployer AWS (Facade)

This module acts as a facade for the AWS deployment logic, which has been refactored 
into modular layers located in `src/aws/deployer_layers/`.

The refactoring splits the monolithic `core_deployer_aws.py` into the following modules:
1.  `layer_1_iot.py`: Contains L1 resources (Dispatcher IAM, Lambda, IoT Rule).
2.  `layer_2_compute.py`: Contains L2 resources (Persister, Event Checker, Step Functions, Event Feedback).
3.  `layer_3_storage.py`: Contains L3 resources (Hot/Cold/Archive Storage, Movers, Readers, Writer, API Gateway).
4.  `layer_4_twinmaker.py`: Contains L4 resources (TwinMaker Workspace, Roles, Buckets).
5.  `layer_5_grafana.py`: Contains L5 resources (Grafana Workspace, Roles, CORS).

This file imports everything from `deployer_layers` to maintain backward compatibility 
with consumers of this module (e.g., `src/deployers/core_deployer.py`).

**Usage:**
Import functions directly from this module as before:
    from aws import core_deployer_aws
    core_deployer_aws.create_dispatcher_lambda_function()
"""

from .deployer_layers import *
