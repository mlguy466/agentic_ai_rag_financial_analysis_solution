#!/usr/bin/env bash
set -euo pipefail

# Deploy the Azure Function in azure_functions/ingest_http
# Usage: APP_NAME=<app> RESOURCE_GROUP=<rg> ./azure_functions/deploy.sh

if ! command -v az >/dev/null 2>&1; then
  echo "az CLI is required. Install: https://aka.ms/azcli"
  exit 2
fi
if ! command -v func >/dev/null 2>&1; then
  echo "Azure Functions Core Tools (func) required. Install: https://learn.microsoft.com/azure/azure-functions/functions-run-local"
  exit 2
fi

: ${APP_NAME:?Need to set APP_NAME environment variable}
: ${RESOURCE_GROUP:?Need to set RESOURCE_GROUP environment variable}
: ${LOCATION:=eastus}

echo "Publishing function to $APP_NAME in $RESOURCE_GROUP ($LOCATION)"

# Ensure logged in
if ! az account show >/dev/null 2>&1; then
  echo "Please run 'az login' before continuing"
  exit 1
fi

# Ensure function app exists (assume linux consumption plan with Python)
EXISTS=$(az functionapp show --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" --query "name" -o tsv 2>/dev/null || echo "")
if [ -z "$EXISTS" ]; then
  echo "Function App $APP_NAME not found in $RESOURCE_GROUP. Create one or change APP_NAME."
  echo "Example creation (requires an existing storage account):"
  echo "  az functionapp create --resource-group $RESOURCE_GROUP --consumption-plan-location $LOCATION --runtime python --runtime-version 3.12 --functions-version 4 --name $APP_NAME --storage-account <STORAGE_ACCOUNT>"
  exit 1
fi

# Publish
pushd azure_functions >/dev/null
func azure functionapp publish "$APP_NAME" --python
popd >/dev/null

# Suggest setting app settings
cat <<EOF
Deployment complete. Next steps:
- In the Azure Portal, confirm the Function App has the following App Settings:
  - AZURE_STORAGE_ACCOUNT_URL=https://<your-account>.blob.core.windows.net
  - AZURE_STORAGE_CONTAINER=filings
  - (Optional) AZURE_BLOB_ONLY_INGESTION=true
- Give the Function App a system-assigned Managed Identity and grant it the 'Storage Blob Data Contributor' role for the storage account.
- Obtain the Function URL and key (Functions -> ingest_http -> Get function URL).
- Trigger once with: curl -X POST "<FUNCTION_URL>?batch_size=50" -d '{}'
EOF
