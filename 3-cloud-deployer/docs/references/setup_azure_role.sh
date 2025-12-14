#!/bin/bash
# =============================================================================
# Azure Custom Role Setup Script for Digital Twin Deployer
# =============================================================================
#
# This script creates a custom Azure role with least-privilege permissions
# required for the Multi-Cloud Digital Twin Deployer.
#
# Prerequisites:
#   - Azure CLI installed and logged in (az login)
#   - Sufficient permissions to create custom roles (Owner or User Access Administrator)
#
# Usage:
#   chmod +x setup_azure_role.sh
#   ./setup_azure_role.sh <subscription_id> <service_principal_object_id>
#
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check arguments
if [ $# -lt 2 ]; then
    echo -e "${RED}Usage: $0 <subscription_id> <service_principal_object_id>${NC}"
    echo ""
    echo "To find your Service Principal Object ID:"
    echo "  az ad sp show --id <client_id> --query id -o tsv"
    echo ""
    echo "To find your Subscription ID:"
    echo "  az account show --query id -o tsv"
    exit 1
fi

SUBSCRIPTION_ID=$1
SP_OBJECT_ID=$2
ROLE_NAME="Digital Twin Deployer"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROLE_FILE="${SCRIPT_DIR}/azure_custom_role.json"

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}Azure Custom Role Setup${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo "Subscription ID: $SUBSCRIPTION_ID"
echo "Service Principal Object ID: $SP_OBJECT_ID"
echo ""

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo -e "${RED}Error: Azure CLI is not installed.${NC}"
    echo "Install from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

# Check if logged in
if ! az account show &> /dev/null; then
    echo -e "${RED}Error: Not logged in to Azure CLI.${NC}"
    echo "Run: az login"
    exit 1
fi

# Set subscription
echo -e "${YELLOW}Setting active subscription...${NC}"
az account set --subscription "$SUBSCRIPTION_ID"

# Check if role already exists
echo -e "${YELLOW}Checking if role already exists...${NC}"
if az role definition list --name "$ROLE_NAME" --query "[0].id" -o tsv 2>/dev/null | grep -q .; then
    echo -e "${YELLOW}Role '$ROLE_NAME' already exists. Updating...${NC}"
    
    # Update the role definition file with subscription ID
    TEMP_ROLE_FILE=$(mktemp)
    sed "s|REPLACE_WITH_YOUR_SUBSCRIPTION_ID|$SUBSCRIPTION_ID|g" "$ROLE_FILE" > "$TEMP_ROLE_FILE"
    
    az role definition update --role-definition "$TEMP_ROLE_FILE"
    rm "$TEMP_ROLE_FILE"
else
    echo -e "${YELLOW}Creating custom role '$ROLE_NAME'...${NC}"
    
    # Update the role definition file with subscription ID
    TEMP_ROLE_FILE=$(mktemp)
    sed "s|REPLACE_WITH_YOUR_SUBSCRIPTION_ID|$SUBSCRIPTION_ID|g" "$ROLE_FILE" > "$TEMP_ROLE_FILE"
    
    az role definition create --role-definition "$TEMP_ROLE_FILE"
    rm "$TEMP_ROLE_FILE"
fi

echo -e "${GREEN}Custom role created/updated successfully!${NC}"

# Assign the role to the service principal with condition
echo -e "${YELLOW}Assigning role to service principal...${NC}"

# Check if assignment already exists
EXISTING_ASSIGNMENT=$(az role assignment list \
    --assignee "$SP_OBJECT_ID" \
    --role "$ROLE_NAME" \
    --scope "/subscriptions/$SUBSCRIPTION_ID" \
    --query "[0].id" -o tsv 2>/dev/null || true)

if [ -n "$EXISTING_ASSIGNMENT" ]; then
    echo -e "${YELLOW}Role assignment already exists.${NC}"
else
    # Get the role definition IDs for the 3 roles the deployer needs to assign
    echo -e "${YELLOW}Looking up role definition IDs...${NC}"
    
    ADT_DATA_OWNER_ID=$(az role definition list \
        --name "Azure Digital Twins Data Owner" \
        --query "[0].name" -o tsv 2>/dev/null || true)
    
    IOT_DATA_CONTRIB_ID=$(az role definition list \
        --name "IoT Hub Data Contributor" \
        --query "[0].name" -o tsv 2>/dev/null || true)
    
    IOT_REGISTRY_CONTRIB_ID=$(az role definition list \
        --name "IoT Hub Registry Contributor" \
        --query "[0].name" -o tsv 2>/dev/null || true)
    
    if [ -z "$ADT_DATA_OWNER_ID" ] || [ -z "$IOT_DATA_CONTRIB_ID" ] || [ -z "$IOT_REGISTRY_CONTRIB_ID" ]; then
        echo -e "${YELLOW}Warning: Could not find one or more role IDs.${NC}"
        echo -e "${YELLOW}Creating assignment without condition (add it manually in Portal).${NC}"
        echo -e "${YELLOW}Required roles: Azure Digital Twins Data Owner, IoT Hub Data Contributor, IoT Hub Registry Contributor${NC}"
        
        az role assignment create \
            --assignee-object-id "$SP_OBJECT_ID" \
            --assignee-principal-type ServicePrincipal \
            --role "$ROLE_NAME" \
            --scope "/subscriptions/$SUBSCRIPTION_ID"
    else
        echo -e "${GREEN}Found role IDs:${NC}"
        echo "  - Azure Digital Twins Data Owner: $ADT_DATA_OWNER_ID"
        echo "  - IoT Hub Data Contributor: $IOT_DATA_CONTRIB_ID"
        echo "  - IoT Hub Registry Contributor: $IOT_REGISTRY_CONTRIB_ID"
        
        # Create with condition to limit which roles can be assigned
        # This condition allows assigning only these 3 specific roles
        CONDITION="(
 (
  !(ActionMatches{'Microsoft.Authorization/roleAssignments/write'})
 )
 OR
 (
  @Request[Microsoft.Authorization/roleAssignments:RoleDefinitionId] ForAnyOfAnyValues:GuidEquals {$ADT_DATA_OWNER_ID, $IOT_DATA_CONTRIB_ID, $IOT_REGISTRY_CONTRIB_ID}
 )
)"
        
        az role assignment create \
            --assignee-object-id "$SP_OBJECT_ID" \
            --assignee-principal-type ServicePrincipal \
            --role "$ROLE_NAME" \
            --scope "/subscriptions/$SUBSCRIPTION_ID" \
            --condition "$CONDITION" \
            --condition-version "2.0"
    fi
    
    echo -e "${GREEN}Role assigned successfully!${NC}"
fi

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo "Your service principal now has the 'Digital Twin Deployer' role."
echo ""
echo "Next steps:"
echo "1. Update your config_credentials.json with Azure credentials"
echo "2. Run: check_credentials azure"
echo ""
echo "Role permissions include:"
echo "  - Resource Groups (create/delete)"
echo "  - Managed Identity (create/delete/assign)"
echo "  - Storage Accounts & Blob Storage"
echo "  - App Service Plans & Function Apps"
echo "  - IoT Hub & Event Grid"
echo "  - Cosmos DB"
echo "  - Azure Digital Twins (including data plane)"
echo "  - Azure Managed Grafana"
echo "  - Role Assignments (for Managed Identity)"
